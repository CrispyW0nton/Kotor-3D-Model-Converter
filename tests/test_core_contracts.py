from __future__ import annotations

import os
from types import MethodType, SimpleNamespace


def test_vertex_space_enum_contract() -> None:
    from src.core.vertex_space import VertexSpace

    assert list(VertexSpace) == [
        VertexSpace.NODE_LOCAL,
        VertexSpace.WORLD,
        VertexSpace.AABB_WALK,
    ]
    assert VertexSpace.NODE_LOCAL == 0
    assert VertexSpace.WORLD == 1
    assert VertexSpace.AABB_WALK == 2


def test_compute_vertex_space_aabb_walkmesh() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0x0200), None) is VertexSpace.AABB_WALK


def test_compute_vertex_space_imported_world() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    node = SimpleNamespace(flags=0, _imported=True)
    assert compute_vertex_space(node, None) is VertexSpace.WORLD


def test_compute_vertex_space_default_node_local() -> None:
    from src.core.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0), None) is VertexSpace.NODE_LOCAL


def test_inner_geometry_name_matching() -> None:
    from src.core.render_constants import is_inner_geometry_name

    for name in ("eyeRA", "teethU", "TongueMesh", "gumskin", "JawSkin", "eyelid"):
        assert is_inner_geometry_name(name)


def test_face_mesh_name_matching() -> None:
    from src.core.render_constants import is_face_mesh_name

    for name in ("head", "Face_LOD0", "fchead01", "skullcap"):
        assert is_face_mesh_name(name)


def test_inner_geometry_does_not_match_non_inner_names() -> None:
    from src.core.render_constants import is_inner_geometry_name

    for name in ("headhook", "model_root", "rootdummy", "random_mesh", ""):
        assert not is_inner_geometry_name(name)


def test_read_mdl_safe_importable_and_callable() -> None:
    from src.core.mdl_reader_wrapper import read_mdl_safe

    assert callable(read_mdl_safe)


def test_pykotor_mdl_binary_fixes_are_idempotent() -> None:
    from src.core.pykotor_mdl_io_fix import ensure_pykotor_mdl_binary_fixes

    ensure_pykotor_mdl_binary_fixes()
    ensure_pykotor_mdl_binary_fixes()


def test_ascii_mdl_nodes_keep_imported_uv_orientation() -> None:
    from src.core.mdl_parser import MDLAsciiParser

    model = MDLAsciiParser().parse(
        [
            "newmodel uv_test",
            "node trimesh mesh",
            "parent NULL",
            "bitmap redtex",
            "bitmap2 greentex",
            "verts 3",
            "0 0 0",
            "1 0 0",
            "0 1 0",
            "tverts 3",
            "0 0",
            "1 0",
            "0 1",
            "faces 1",
            "0 1 2 1 0 1 2 0",
            "endnode",
            "donemodel",
        ]
    )

    assert model.root_node is not None
    assert model.root_node.texture_names == ["redtex", "greentex"]
    assert model.root_node.uvs == [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    assert model.root_node.imported_ascii is True
    assert model.root_node.uv_v_flip is True
    assert model.root_node.face_mats == [0]


def test_gpu_shader_has_per_node_uv_v_flip_control() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _VERT_SRC

    assert "uniform float u_uv_v_flip" in _VERT_SRC
    assert "mix(in_uv.y, 1.0 - in_uv.y, u_uv_v_flip)" in _VERT_SRC


def test_gpu_ascii_multitexture_split_is_ascii_gated() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer

    source = inspect.getsource(GpuRenderer._render_gpu)
    assert "ASCII/Kotor Tool MDLs use face_mats as per-face texture slots" in source
    assert "getattr(node, 'imported_ascii', False)" in source
    assert "gm.mat_slots" in source


def test_qt_gpu_viewport_uses_overlay_not_cpu_textured_fallback() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._draw_cpu_overlays)
    assert "_draw_mesh_textured" not in source
    assert "not gpu_base" in source
    assert "_draw_grid" in source
    assert "_draw_stats" in source


def test_qt_gpu_viewport_keeps_gpu_for_wire_and_texture_off_modes() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    frame_source = inspect.getsource(QtViewportWidget._render_frame)
    gpu_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert "self._renderer.show_solid or self._renderer.show_wireframe" in frame_source
    assert "and self._renderer.show_texture" not in frame_source
    assert "show_texture = bool(self._renderer.show_texture)" in gpu_source
    assert "show_wireframe = bool(self._renderer.show_wireframe)" in gpu_source


def test_gpu_renderer_supports_texture_off_and_wireframe_modes() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)

    assert "self.show_texture: bool = True" in init_source
    assert "self.show_solid: bool = True" in init_source
    assert "self.wire_color: tuple[float, float, float] = (0.18, 0.62, 0.95)" in init_source
    assert "_texture_allowed = bool(self.show_texture)" in render_source
    assert "ctx.wireframe = bool(self.show_wireframe and not self.show_solid)" in render_source
    assert "if self.show_solid and self.show_wireframe" in render_source
    assert "u_wireframe_enabled" in render_source
    assert "u_wire_color" in render_source


def test_gpu_renderer_exposes_module_render_modes_and_selection_tint() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer, _FRAG_SRC
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    viewport_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert 'self.render_mode: str = "realistic"' in init_source
    assert "uniform int   u_render_mode" in _FRAG_SRC
    assert "uniform int   u_selected" in _FRAG_SRC
    assert "u_render_mode == 1" in _FRAG_SRC
    assert "u_render_mode == 2" in _FRAG_SRC
    assert "soft_shade" in _FRAG_SRC
    assert "0.76 + max(dot(N, u_light_dir), 0.0) * 0.24" in _FRAG_SRC
    assert "mix(lit_color, vec3(1.0, 0.78, 0.12), 0.45)" in _FRAG_SRC
    assert "getattr(node, '_gr_hidden', False)" in render_source
    assert "_detail_texture_allowed = bool(_texture_allowed and _render_mode_int == 0)" in render_source
    assert "if _gpu_is_module and _render_mode_int in (1, 2)" in render_source
    assert "render_mode = str(getattr(self._renderer" in viewport_source
    assert "selected_node = getattr(self._renderer" in viewport_source
    assert "selected_nodes = list(getattr(self, \"_selected_meshes\"" in viewport_source
    assert "_texture_allowed = bool(self.show_texture)" in render_source


def test_module_mesh_properties_panel_lists_selects_and_hides_meshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    mesh_a = SimpleNamespace(
        name="room_a",
        is_mesh=True,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="wall01",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    mesh_b = SimpleNamespace(
        name="room_b",
        is_mesh=True,
        vertices=[(0, 0, 0)],
        faces=[],
        texture="greybox",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [mesh_a, mesh_b],
        all_nodes=lambda: [mesh_a, mesh_b],
        bone_nodes=lambda: [],
        texture_list=lambda: ["wall01", "greybox"],
    )

    selected = []
    panel.moduleMeshSelected.connect(selected.append)
    panel.show_model(model)

    assert panel.module_mesh_tree.topLevelItemCount() == 2
    panel.module_mesh_tree.setCurrentItem(panel.module_mesh_tree.topLevelItem(0))
    assert selected[-1] is mesh_a

    panel._set_selected_meshes_hidden(True)
    assert mesh_a._gr_hidden is True
    assert panel.module_mesh_tree.topLevelItem(0).text(4) == "no"

    panel.module_mesh_tree.topLevelItem(0).setSelected(True)
    panel._hide_unselected_module_meshes()
    assert mesh_b._gr_hidden is True


def test_module_mesh_properties_panel_supports_multi_select_all() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    meshes = [
        SimpleNamespace(
            name=f"mesh_{index}",
            is_mesh=True,
            vertices=[(0, 0, 0)],
            faces=[(0, 0, 0)],
            texture="tex",
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
        for index in range(3)
    ]
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: meshes,
        all_nodes=lambda: meshes,
        bone_nodes=lambda: [],
        texture_list=lambda: ["tex"],
    )
    selected_batches = []
    panel.moduleMeshesSelected.connect(selected_batches.append)

    panel.show_model(model)
    panel.select_all_module_meshes()

    assert len(panel._selected_module_meshes()) == 3
    assert selected_batches[-1] == meshes


def test_module_mesh_properties_panel_splits_meshes_and_walkmeshes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    regular_mesh = SimpleNamespace(
        name="regular_mesh",
        is_mesh=True,
        vertices=[(0, 0, 0)],
        faces=[(0, 0, 0)],
        texture="wall",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    grey_geometry = SimpleNamespace(
        name="walkmesh_12",
        is_mesh=False,
        vertex_space=2,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [regular_mesh],
        all_nodes=lambda: [regular_mesh, grey_geometry],
        bone_nodes=lambda: [],
        texture_list=lambda: ["wall"],
    )

    panel.show_model(model)

    mesh_names = [
        panel.module_mesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_mesh_tree.topLevelItemCount())
    ]
    walkmesh_names = [
        panel.module_walkmesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_walkmesh_tree.topLevelItemCount())
    ]
    assert mesh_names == ["regular_mesh"]
    assert walkmesh_names == ["walkmesh_12"]
    assert panel.module_browser_tabs.tabText(1) == "Walkmeshes"


def test_qt_viewport_exposes_mesh_multiselect_box_and_ctrl_a() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget)

    assert "meshSelectionChanged = QtCore.Signal(list)" in source
    assert "def set_selected_meshes" in source
    assert "def select_all_meshes" in source
    assert "QtCore.Qt.Key_A" in source
    assert "def _mesh_nodes_in_rect" in source
    assert "def _all_geometry_nodes" in source
    assert "def _is_selectable_mesh_node" in source
    assert "QtWidgets.QRubberBand" in source
    assert "def _front_facing_score" in source
    assert "def _point_in_triangle" in source


def test_qt_viewport_context_menu_does_not_pick_on_right_click() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._show_mesh_context_menu)
    hide_source = inspect.getsource(QtViewportWidget._set_selected_meshes_hidden)

    assert "self.set_selected_node(node)" not in source
    assert "if not self._selected_meshes" not in source
    assert "node is not None and id(node) not in selected_ids" in source
    assert "Hide Selected" in source
    assert "unhide_all_action.setEnabled(self.model is not None)" in source
    assert "_set_selected_meshes_hidden(True)" in source
    assert "self.set_selected_meshes([])" not in hide_source


def test_qt_gpu_viewport_disables_gpu_culling_for_cpu_parity() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    assert "cull_faces = False" in source


def test_viewport_navigation_profiles_are_available() -> None:
    from src.gui.qt_lib.rendering.viewport_navigation import (
        DEFAULT_VIEWPORT_NAVIGATION_PROFILE,
        VIEWPORT_NAVIGATION_HELP,
        VIEWPORT_NAVIGATION_PROFILES,
        normalize_viewport_navigation_profile,
    )

    assert set(VIEWPORT_NAVIGATION_PROFILES) == {"3dsmax", "blender", "maya"}
    assert DEFAULT_VIEWPORT_NAVIGATION_PROFILE == "maya"
    assert normalize_viewport_navigation_profile("3ds Max") == "3dsmax"
    assert normalize_viewport_navigation_profile("Blender") == "blender"
    assert normalize_viewport_navigation_profile("Maya") == "maya"
    assert "T: Toggle texture" in VIEWPORT_NAVIGATION_HELP
    assert "Shift+T: Top view" in VIEWPORT_NAVIGATION_HELP
    assert "Alt+X: Toggle X-Ray viewport overlay" in VIEWPORT_NAVIGATION_HELP


def test_qt_viewport_uses_profiled_navigation_actions() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._navigation_action)
    assert 'profile == "3dsmax"' in source
    assert 'profile == "blender"' in source
    assert 'profile == "maya"' in source
    assert "QtCore.Qt.AltModifier" in source


def test_qt_viewport_gpu_grid_is_native_and_xray_is_overlay_only() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    gpu_source = inspect.getsource(GpuRenderer._draw_grid)
    assert "ctx.depth_mask = False" in gpu_source
    assert "vao.render(moderngl.LINES)" in gpu_source
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    assert "self._draw_grid(ctx, mvp)" in render_source
    overlay_source = inspect.getsource(QtViewportWidget._draw_cpu_overlays)
    assert "self._xray_mode or not gpu_base" in overlay_source
    event_source = inspect.getsource(QtViewportWidget.eventFilter)
    assert "QtCore.Qt.Key_X" in event_source
    assert "QtCore.Qt.AltModifier" in event_source


def test_qt_animations_panel_can_select_loaded_animation() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    model = SimpleNamespace(
        animations=[
            SimpleNamespace(name="pause1"),
            SimpleNamespace(name="walkss"),
        ]
    )

    panel.load_model(model, select_name="walkss")

    assert panel.selected_animation() == "walkss"
    assert panel.info.toPlainText() == "2 animation(s)"


def test_qt_animations_panel_exposes_bake_and_binary_export_actions() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    labels = {button.text() for button in panel.findChildren(QtWidgets.QPushButton)}

    assert "Bake Animation" in labels
    assert "Export Binary MDL" in labels


def test_main_window_moves_rig_panel_to_modules_window() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_rig_panel import QtRigWindow
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert 'right_tabs.addTab(self.rig_panel' not in source
    assert "self.rig_window = QtRigWindow(self)" in source
    assert "self.rig_panel = self.rig_window.panel" in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert "self.rig_window_action" in actions_source
    assert "self._open_rig_window" in actions_source

    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    assert "modules_menu.addAction(self.rig_window_action)" in menu_source

    open_source = inspect.getsource(QtGhostRiggerMainWindow._open_rig_window)
    assert "window.show()" in open_source
    assert "window.raise_()" in open_source
    assert QtRigWindow.__name__ == "QtRigWindow"
    assert hasattr(QtRigWindow, "rigActionRequested")


def test_main_window_moves_utility_tabs_to_tools_windows() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_diagnostics_panel import QtDiagnosticsWindow
    from src.gui.qt_lib.panels.qt_texture_panel import QtTextureToolWindow
    from src.gui.qt_lib.windows.qt_blueprint_editor import QtBlueprintEditorWindow
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    for tab_expr in (
        "right_tabs.addTab(self.texture_panel",
        "right_tabs.addTab(self.normal_map_panel",
        "right_tabs.addTab(self.diagnostics_panel",
        "right_tabs.addTab(self.blueprint_panel",
    ):
        assert tab_expr not in source
    assert "self.texture_tool_window = QtTextureToolWindow(self)" in source
    assert "self.diagnostics_window = QtDiagnosticsWindow(self._get_model, self)" in source
    assert "self.blueprint_window = QtBlueprintEditorWindow(self)" in source
    assert "self.texture_panel = self.texture_tool_window.texture_panel" in source
    assert "self.normal_map_panel = self.texture_tool_window.normal_map_panel" in source
    assert "self.diagnostics_panel = self.diagnostics_window.panel" in source
    assert "self.blueprint_panel = self.blueprint_window.panel" in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert "self.texture_tool_action" in actions_source
    assert "self.blueprint_editor_action" in actions_source
    assert "self._open_texture_tool_window" in actions_source
    assert "self._open_blueprint_editor_window" in actions_source

    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    assert "tools_menu.addAction(self.diag_action)" in menu_source
    assert "tools_menu.addAction(self.texture_tool_action)" in menu_source
    assert "tools_menu.addAction(self.blueprint_editor_action)" in menu_source

    model_menu_block = menu_source.split("mdlops_menu = self.menuBar().addMenu", 1)[0]
    assert "self.diag_action" not in model_menu_block

    for method_name in (
        "_show_diagnostics_panel",
        "_open_texture_tool_window",
        "_open_blueprint_editor_window",
    ):
        open_source = inspect.getsource(getattr(QtGhostRiggerMainWindow, method_name))
        assert "window.show()" in open_source
        assert "window.raise_()" in open_source

    assert QtDiagnosticsWindow.__name__ == "QtDiagnosticsWindow"
    assert QtTextureToolWindow.__name__ == "QtTextureToolWindow"
    assert QtBlueprintEditorWindow.__name__ == "QtBlueprintEditorWindow"


def test_main_window_combines_animation_tabs_and_removes_builder_tab() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_animation_panel import QtAnimationLibraryCombinedPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "self.animation_library_combined_panel = QtAnimationLibraryCombinedPanel(" in source
    assert 'right_tabs.addTab(self.animation_library_combined_panel, self._icon("anims", 16), "Animation Library")' in source
    assert "right_tabs.addTab(self.animations_panel" not in source
    assert "right_tabs.addTab(self.animation_library_panel" not in source
    assert "right_tabs.addTab(self.character_builder_panel" not in source
    assert "self.character_builder_panel = QtCharacterBuilderPanel" not in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert '"Animation Library"' in actions_source
    assert 'self._show_right_tab("Animation Library")' in actions_source

    module_source = inspect.getsource(QtGhostRiggerMainWindow._handle_module_action)
    assert 'self._open_blueprint_editor_window()' in module_source
    assert 'self._show_right_tab("Blueprint")' not in module_source

    assert QtAnimationLibraryCombinedPanel.__name__ == "QtAnimationLibraryCombinedPanel"


def test_main_window_bottom_area_is_resizable_splitter() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)" in source
    assert "self.vertical_splitter = vertical_splitter" in source
    assert "vertical_splitter.addWidget(main_splitter)" in source
    assert "vertical_splitter.addWidget(self.log_panel)" in source
    assert "root.addWidget(vertical_splitter, 1)" in source
    assert "root.addWidget(main_splitter, 1)" not in source
    assert "root.addWidget(self.log_panel, 0)" not in source
    assert "vertical_splitter.setSizes([720, 240])" in source


def test_main_window_exposes_animation_helpers_to_python_terminal() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "self._configure_python_terminal_context()" in layout_source

    context_source = inspect.getsource(QtGhostRiggerMainWindow._configure_python_terminal_context)
    for helper in (
        "model=self._terminal_model",
        "selected_model=self._terminal_model",
        "animation_names=self._terminal_animation_names",
        "select_animation=self._terminal_select_animation",
        "play_animation=self._terminal_play_animation",
        "stop_animation=self._terminal_stop_animation",
        "seek_animation=self._terminal_seek_animation",
        "override_animation=self._terminal_override_animation",
    ):
        assert helper in context_source

    play_source = inspect.getsource(QtGhostRiggerMainWindow._terminal_play_animation)
    assert 'self._handle_animation_action("Play", anim_name)' in play_source

    override_source = inspect.getsource(QtGhostRiggerMainWindow._terminal_override_animation)
    assert "copy.deepcopy(source_anim)" in override_source
    assert "model.animations = animations" in override_source
    assert "self.animations_panel.load_model(model, select_name=target_name)" in override_source


def test_qt_main_window_builds_baked_animation_clip() -> None:
    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    root = ModelNode(name="rootdummy")
    head = ModelNode(name="head")
    root.children.append(head)
    head.parent = root
    anim_node = ModelNode(name="head")
    anim_node.controllers = [
        {
            "type": 8,
            "name": "position",
            "columns": 3,
            "times": [0.0, 1.0],
            "values": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
        }
    ]
    model = KotorModel(name="BakeTest", root_node=root)
    model.animations = [Animation(name="move", length=1.0, nodes=[anim_node])]

    baked = QtGhostRiggerMainWindow._build_baked_animation(
        SimpleNamespace(),
        model,
        "move",
        "move_baked",
        fps=2,
    )

    assert baked.name == "move_baked"
    assert len(baked.nodes) == 1
    ctrl = baked.nodes[0].controllers[0]
    assert ctrl["type"] == 8
    assert ctrl["times"] == [0.0, 0.5, 1.0]
    assert ctrl["values"] == [[0.0, 0.0, 0.0], [0.5, 0.0, 0.0], [1.0, 0.0, 0.0]]


def test_mdl_porter_animation_nodes_are_serialized_as_dummy_nodes() -> None:
    from src.core.mdl_porter import MDLBinaryWriter
    from src.core.model_data import ModelNode, NodeFlags

    anim_node = ModelNode(name="robe", flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN))
    anim_node.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]

    block = MDLBinaryWriter()._build_anim_node(anim_node, [anim_node], False, 168)

    assert int.from_bytes(block[0:2], "little") == int(NodeFlags.HEADER)


def test_mdl_porter_rebuilds_flat_animation_nodes_as_reachable_tree() -> None:
    from src.core.mdl_porter import MDLBinaryWriter
    from src.core.model_data import Animation, ModelNode

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis")
    head = ModelNode(name="head")
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(head)
    head.parent = pelvis

    anim_head = ModelNode(name="head")
    anim_head.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]
    anim = Animation(name="look", nodes=[anim_head])

    nodes = MDLBinaryWriter()._animation_nodes_with_hierarchy(anim, [root, pelvis, head])

    assert [node.name for node in nodes] == ["root", "pelvis", "head"]
    assert nodes[1].parent is nodes[0]
    assert nodes[2].parent is nodes[1]
    assert nodes[2].controllers == anim_head.controllers


def test_mdl_writer_skin_palette_uses_emitted_node_indices() -> None:
    from src.core.mdl_writer import MDLBinaryWriter

    writer = MDLBinaryWriter()
    writer._node_index_by_name = {
        "root": 0,
        "cape05_g": 14,
        "rforearm_g": 27,
    }

    assert writer._skin_bone_node_index("Cape05_g") == 14
    assert writer._skin_bone_node_index("RForeArm_G") == 27
    assert writer._skin_bone_node_index("") == -1


def test_mdl_writer_rebuilds_flat_animation_nodes_as_reachable_tree() -> None:
    from src.core.mdl_writer import MDLBinaryWriter
    from src.core.model_data import Animation, ModelNode

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis")
    head = ModelNode(name="head")
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(head)
    head.parent = pelvis

    anim_head = ModelNode(name="head")
    anim_head.controllers = [
        {
            "type": 20,
            "name": "orientation",
            "columns": 4,
            "times": [0.0],
            "values": [[0.0, 0.0, 0.0, 1.0]],
        }
    ]
    anim = Animation(name="look", nodes=[anim_head])

    nodes = MDLBinaryWriter()._animation_nodes_with_hierarchy(anim, [root, pelvis, head])

    assert [node.name for node in nodes] == ["root", "pelvis", "head"]
    assert nodes[1].parent is nodes[0]
    assert nodes[2].parent is nodes[1]
    assert nodes[2].controllers == anim_head.controllers


def test_binary_mdl_export_uses_skin_aware_writer() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._export_mdl_binary)

    assert "from src.core.mdl_writer import MDLBinaryWriter" in source


def test_retarget_apply_promotes_target_model_for_animation_list() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    window = SimpleNamespace()
    target = SimpleNamespace(name="N_Bith", mdl_path="")
    calls = []
    window._retarget_target_model = target
    window._current_model = SimpleNamespace(name="N_DarthMalak")
    window._current_game = "K1"
    window.animation_retarget_panel = SimpleNamespace(_target_game="K2")
    window._infer_game_from_model = lambda _model: "K1"
    window._set_model_internal = lambda model, path="": calls.append(("set", model, path))
    window._populate_animation_library_from_current_model = lambda: calls.append(("populate",))
    window._show_right_tab = lambda label: calls.append(("tab", label))
    window.animations_panel = SimpleNamespace(
        select_animation=lambda name: calls.append(("select", name))
    )
    window._retarget_target_label = MethodType(
        QtGhostRiggerMainWindow._retarget_target_label,
        window,
    )

    QtGhostRiggerMainWindow._activate_retarget_target_model(window, "walkss")

    assert ("set", target, "K2:N_Bith") in calls
    assert ("populate",) in calls
    assert ("select", "walkss") in calls
    assert ("tab", "Animations") in calls


def test_quinn_bone_map_loads_as_unreal_target_model() -> None:
    import pytest

    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    asset = load_quinn_skeleton_asset()
    model = unreal_skeleton_model(asset)
    names = {node.name.lower() for node in model.all_nodes()}

    assert asset.name == "SKM_Quinn_Simple"
    assert 80 <= asset.bone_count < 100
    assert asset.source == "SKM_Quinn_Simple.FBX"
    assert {"root", "pelvis", "spine_01", "head", "hand_l", "hand_r"} <= names
    assert model.find_node("spine_01").parent is model.find_node("pelvis")
    assert model.find_node("clavicle_out_l") is None


def test_quinn_fbx_import_loads_viewport_mesh() -> None:
    import pytest

    from src.unreal.quinn import QUINN_FBX, load_quinn_fbx_model, load_quinn_skeleton_asset

    if not QUINN_FBX.exists():
        pytest.skip("SKM_Quinn_Simple.FBX not available")

    model = load_quinn_fbx_model(load_quinn_skeleton_asset())
    meshes = model.mesh_nodes()

    assert model.name == "SKM_Quinn_Simple"
    assert len(meshes) == 1
    assert len(meshes[0].vertices) > 40_000
    assert len(meshes[0].faces) > 80_000
    assert meshes[0].is_skin
    assert len(meshes[0].skin_data) == len(meshes[0].vertices)
    assert len(meshes[0].bone_map) > 60
    assert all(sd.influences for sd in meshes[0].skin_data)
    assert all(abs(sum(inf.weight for inf in sd.influences) - 1.0) < 1e-5 for sd in meshes[0].skin_data)
    assert meshes[0].uvs[0][1] > 0.7
    assert "MI_Quinn_01_BaseColor_0" in meshes[0].texture_names
    assert "MI_Quinn_02_BaseColor_1" in meshes[0].texture_names
    assert model.find_node("pelvis") is not None
    assert model.find_node("spine_01").parent is model.find_node("pelvis")
    assert model.find_node("head").bone_world_position()[2] > model.find_node("pelvis").bone_world_position()[2]
    assert not getattr(model.find_node("pelvis"), "_hide_skeleton_overlay", False)
    assert model.find_node("clavicle_out_l") is None

    uncorrected = load_quinn_fbx_model(load_quinn_skeleton_asset(), yaw_180=False)
    assert meshes[0].vertices[0][0] == pytest.approx(-uncorrected.mesh_nodes()[0].vertices[0][0])
    assert meshes[0].vertices[0][1] == pytest.approx(-uncorrected.mesh_nodes()[0].vertices[0][1])
    assert meshes[0].vertices[0][2] == pytest.approx(uncorrected.mesh_nodes()[0].vertices[0][2])


def test_quinn_control_bones_do_not_enter_viewport_skeleton_overlay() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer
    from src.unreal.quinn import QUINN_FBX, load_quinn_fbx_model, load_quinn_skeleton_asset

    if not QUINN_FBX.exists():
        pytest.skip("SKM_Quinn_Simple.FBX not available")

    model = load_quinn_fbx_model(load_quinn_skeleton_asset())
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)
    renderer._proj = lambda x, y, z, w, h: (int(100 + x * 10), int(100 - z * 10), y)

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_bones(ImageDraw.Draw(img), 240, 240)
    names = {getattr(node, "name", "").lower() for *_screen, node in renderer._bone_screen_positions}

    assert "pelvis" in names
    assert "ik_foot_root" not in names
    assert "ik_hand_root" not in names
    assert "interaction" not in names
    assert "center_of_mass" not in names


def test_quinn_aliases_map_common_kotor_supermodel_bones() -> None:
    import pytest

    from src.core.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map
    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="pelvis_g"),
            ModelNode(name="spine_g"),
            ModelNode(name="torso_g"),
            ModelNode(name="torsoUpr_g"),
            ModelNode(name="rCollar_g"),
            ModelNode(name="rbicepl_g"),
            ModelNode(name="lforearm"),
            ModelNode(name="rhand"),
            ModelNode(name="rthigh"),
            ModelNode(name="lshin_g"),
            ModelNode(name="rfootT_g"),
        ],
    )
    target = unreal_skeleton_model(load_quinn_skeleton_asset())

    report = build_bone_map(source, target)

    assert report.mapping["pelvis_g"] == "pelvis"
    assert report.mapping["spine_g"] == "spine_01"
    assert report.mapping["torso_g"] == "spine_02"
    assert report.mapping["torsoupr_g"] in {"spine_03", "spine_04", "spine_01"}
    assert report.mapping["rcollar_g"] == "clavicle_r"
    assert report.mapping["rbicepl_g"] == "lowerarm_r"
    assert report.mapping["lforearm"] == "lowerarm_l"
    assert report.mapping["rhand"] == "hand_r"
    assert report.mapping["rthigh"] == "thigh_r"
    assert report.mapping["lshin_g"] == "calf_l"
    assert report.mapping["rfoott_g"] == "ball_r"


def test_unreal_bone_map_excludes_dummy_and_hook_helpers() -> None:
    from src.core.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="rootdummy"),
            ModelNode(name="talkdummy"),
            ModelNode(name="headhook"),
            ModelNode(name="pelvis_g"),
        ],
    )
    target = SimpleNamespace(
        name="SKM_Quinn_Simple",
        all_nodes=lambda: [
            ModelNode(name="root"),
            ModelNode(name="dummyroot"),
            ModelNode(name="headhook"),
            ModelNode(name="pelvis"),
        ],
    )

    report = build_bone_map(
        source,
        target,
        manual_mapping={
            "rootdummy": "root",
            "talkdummy": "root",
            "headhook": "headhook",
            "pelvis_g": "dummyroot",
        },
    )

    assert "rootdummy" not in report.mapping
    assert "talkdummy" not in report.mapping
    assert "headhook" not in report.mapping
    assert "rootdummy" not in report.missing_source
    assert "talkdummy" not in report.missing_source
    assert "headhook" not in report.missing_source
    assert report.mapping["pelvis_g"] == "pelvis"


def test_unreal_viewport_hides_dummy_and_hook_helpers_from_bone_overlay() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    root = ModelNode(name="root")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 1.0))
    talkdummy = ModelNode(name="talkdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 3.0))
    headhook = ModelNode(name="headhook", position=(0.0, 0.0, 3.0))
    root.children.extend([pelvis, headhook])
    pelvis.parent = root
    pelvis.children.append(talkdummy)
    talkdummy.parent = pelvis
    talkdummy.children.append(torso)
    torso.parent = talkdummy
    headhook.parent = root

    model = KotorModel(name="S_Male02", root_node=root)
    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)
    renderer.set_hidden_bone_name_fragments(("dummy", "hook"))
    renderer._proj = lambda x, y, z, w, h: (int(100 + z * 10), 100, z)

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_bones(ImageDraw.Draw(img), 240, 240)
    names = {getattr(node, "name", "").lower() for *_screen, node in renderer._bone_screen_positions}

    assert "root" in names
    assert "pelvis_g" in names
    assert "torso_g" in names
    assert "talkdummy" not in names
    assert "headhook" not in names


def test_unreal_viewport_hidden_helper_selection_does_not_draw_gimbal() -> None:
    import pytest

    pytest.importorskip("PIL")

    from PIL import Image, ImageDraw

    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    root = ModelNode(name="root")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 1.0))
    root.children.append(rootdummy)
    rootdummy.parent = root

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(KotorModel(name="S_Male02", root_node=root))
    renderer.set_hidden_bone_name_fragments(("dummy", "hook"))
    renderer.selected_node = rootdummy
    renderer._gimbal_handles = [(10, 10, "X")]

    img = Image.new("RGB", (240, 240), "black")
    renderer._draw_gimbal(ImageDraw.Draw(img), 240, 240)

    assert renderer.selected_node is None
    assert renderer._gimbal_handles == []


def test_unreal_animator_inserts_synthetic_spine_between_pelvis_and_torso() -> None:
    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True

    spine = model.find_node("spine_g")
    assert spine is not None
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert torso in spine.children
    assert torso not in rootdummy.children
    assert spine.position == (0.0, 0.0, 3.0)
    assert torso.position == (0.0, 0.0, 3.0)


def test_unreal_animator_inserts_synthetic_spine_when_pelvis_and_torso_share_rootdummy() -> None:
    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 0.0))
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.append(rootdummy)
    rootdummy.parent = root
    rootdummy.children.extend([pelvis, torso])
    pelvis.parent = rootdummy
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True

    spine = model.find_node("spine_g")
    assert spine is not None
    assert pelvis.parent is rootdummy
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert spine in pelvis.children
    assert torso in spine.children
    assert torso not in rootdummy.children
    assert spine.position == (0.0, 0.0, 3.0)
    assert torso.position == (0.0, 0.0, 3.0)


def test_unreal_animator_repositions_existing_spine_between_pelvis_and_torso() -> None:
    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    spine = ModelNode(name="spine_g", position=(99.0, 99.0, 99.0))
    root.children.extend([pelvis, spine])
    pelvis.parent = root
    spine.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow.__new__(QtUnrealAnimatorWindow)

    assert window._ensure_source_spine_g(model) is True
    assert spine.parent is pelvis
    assert torso.parent is spine
    assert spine in pelvis.children
    assert torso in spine.children
    assert spine not in root.children


def test_unreal_animator_source_bone_browser_lists_and_selects_spine() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 2.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 4.0))
    root.children.append(pelvis)
    pelvis.parent = root
    pelvis.children.append(rootdummy)
    rootdummy.parent = pelvis
    rootdummy.children.append(torso)
    torso.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        rows = {
            window.source_bones.topLevelItem(row).text(0): window.source_bones.topLevelItem(row)
            for row in range(window.source_bones.topLevelItemCount())
        }

        assert "spine_g" in rows
        assert "rootdummy" not in rows
        assert rows["spine_g"].text(1) == "pelvis_g"
        assert rows["spine_g"].text(2) == "synthetic"

        window.source_bones.setCurrentItem(rows["spine_g"])
        assert getattr(window.source_viewport._renderer.selected_node, "name", "") == "spine_g"
    finally:
        window.close()


def test_unreal_animator_manually_adds_and_deletes_source_synthetic_bones() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    rootdummy = ModelNode(name="rootdummy", position=(0.0, 0.0, 0.0))
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    torso_upper = ModelNode(name="torsoUpr_g", position=(0.0, 0.0, 4.0))
    neck = ModelNode(name="neck_g", position=(0.0, 0.0, 6.0))
    eyelid = ModelNode(name="eyelid", position=(1.0, 0.0, 7.0))
    root.children.append(rootdummy)
    rootdummy.parent = root
    rootdummy.children.extend([pelvis, torso, eyelid])
    pelvis.parent = rootdummy
    torso.parent = rootdummy
    torso.children.append(torso_upper)
    torso_upper.parent = torso
    torso_upper.children.append(neck)
    neck.parent = torso_upper
    eyelid.parent = rootdummy
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [object()]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")

        assert model.find_node("spine_05") is None
        assert model.find_node("lowerarm_twist_01_l") is None
        assert model.find_node("ik_foot_root") is None
        assert model.find_node("interaction") is None
        assert model.find_node("center_of_mass") is None

        spacer = window._add_source_synthetic_bone("spine_05", child_node=neck)
        assert spacer is not None
        assert spacer.name == "spine_05"
        assert spacer.parent is torso_upper
        assert neck.parent is spacer
        assert bool(getattr(spacer, "_ghostrigger_synthetic_unreal_source", False))
        assert bool(getattr(spacer, "_ghostrigger_synthetic_manual_source", False))
        assert spacer.position == (0.0, 0.0, 3.0)
        assert neck.position == (0.0, 0.0, 3.0)

        rows = {
            window.source_bones.topLevelItem(row).text(0): window.source_bones.topLevelItem(row)
            for row in range(window.source_bones.topLevelItemCount())
        }
        assert "pelvis_g" in rows
        assert "torso_g" in rows
        assert "torsoUpr_g" in rows
        assert "neck_g" in rows
        assert "eyelid" in rows
        assert "spine_05" in rows
        assert "ik_foot_root" not in rows
        assert rows["spine_05"].text(2) == "synthetic"
        assert "Quinn bones" not in window.source_label.text()

        window.source_bones.setCurrentItem(rows["spine_05"])
        assert window._delete_selected_source_synthetic_bone() is True
        assert model.find_node("spine_05") is None
        assert neck.parent is torso_upper
        assert neck.position == (0.0, 0.0, 6.0)
    finally:
        window.close()


def test_unreal_animator_exposes_reload_code_button() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    window = QtUnrealAnimatorWindow()
    try:
        assert window.reload_code_action.shortcut().toString() == "Ctrl+Shift+R"
        assert window.reload_code_button.text() == "Reload Code"
        with_signal = []
        window.reloadCodeRequested.connect(lambda: with_signal.append(True))

        window.reload_code_button.click()

        assert with_signal == [True]
    finally:
        window.close()


def test_unreal_animator_animation_selection_arms_preview_pose() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.extend([pelvis, torso])
    pelvis.parent = root
    torso.parent = root
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [
        Animation(name="pause1", length=1.0),
        Animation(name="taunt", length=1.6),
    ]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        window.anim_list.setCurrentRow(1)

        assert window.selected_animation_name() == "taunt"
        assert window._preview_engine is not None
        assert window._preview_engine.current_animation.name == "taunt"
        assert not window._preview_timer.isActive()
        assert window.preview_button.isEnabled()
        assert window.source_frame_label.text() == "0 / 48f"
        assert window.target_frame_label.text() == "0 / 48f"
    finally:
        window.close()


def test_unreal_animator_uses_gpu_during_animation_preview() -> None:
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_lib.windows.qt_unreal_animator import QtUnrealAnimatorWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    root = ModelNode(name="s_female03")
    pelvis = ModelNode(name="pelvis_g", position=(0.0, 0.0, 10.0))
    torso = ModelNode(name="torso_g", position=(0.0, 0.0, 16.0))
    root.children.extend([pelvis, torso])
    pelvis.parent = root
    torso.parent = root
    model = KotorModel(name="S_Female03", root_node=root)
    model.animations = [Animation(name="pause1", length=1.0)]

    window = QtUnrealAnimatorWindow()
    try:
        window.set_source_model(model, "K1")
        window.source_viewport.toggle_gpu_renderer(False)
        window.target_viewport.toggle_gpu_renderer(False)

        window.preview_selected_animation()

        assert window.source_viewport._use_gpu is True
        assert window.target_viewport._use_gpu is True

        window.stop_preview()

        assert window.source_viewport._use_gpu is False
        assert window.target_viewport._use_gpu is False
    finally:
        window.close()


def test_retarget_pose_applies_source_bind_relative_rotation_to_target_bind() -> None:
    import math

    import pytest

    from src.core.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting import retarget_pose
    from src.core.model_data import ModelNode

    src_bind = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    target_bind = (0.0, math.sin(math.radians(15.0)), 0.0, math.cos(math.radians(15.0)))
    source = SimpleNamespace(name="source", all_nodes=lambda: [ModelNode(name="RHand", rotation=src_bind)])
    target = SimpleNamespace(name="target", all_nodes=lambda: [ModelNode(name="RHand", rotation=target_bind)])
    pose = AnimPose(nodes={"rhand": NodePose(name="RHand", rotation=src_bind)})

    result = retarget_pose(pose, source, target)

    assert result.pose.nodes["rhand"].rotation == pytest.approx(target_bind)


def test_manual_bone_map_override_drives_retarget_pose() -> None:
    from src.core.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting import build_bone_map, retarget_pose
    from src.core.model_data import ModelNode

    source = SimpleNamespace(name="source", all_nodes=lambda: [ModelNode(name="source_arm")])
    target = SimpleNamespace(name="target", all_nodes=lambda: [ModelNode(name="target_arm")])

    report = build_bone_map(source, target, manual_mapping={"source_arm": "target_arm"})
    result = retarget_pose(
        AnimPose(nodes={"source_arm": NodePose(name="source_arm")}),
        source,
        target,
        mapping_report=report,
    )

    assert report.manual_matches == 1
    assert report.mapping == {"source_arm": "target_arm"}
    assert "target_arm" in result.pose.nodes


def test_preserve_model_scale_scales_position_deltas_by_target_height() -> None:
    import pytest

    from src.core.animation_engine import AnimPose, NodePose
    from src.core.animation_retargeting import RetargetConfig, retarget_pose
    from src.core.model_data import KotorModel, ModelNode

    src_root = ModelNode(name="root")
    src_head = ModelNode(name="head", position=(0.0, 0.0, 10.0))
    src_root.children.append(src_head)
    src_head.parent = src_root
    source = KotorModel(name="source", root_node=src_root)

    dst_root = ModelNode(name="root")
    dst_head = ModelNode(name="head", position=(0.0, 0.0, 5.0))
    dst_root.children.append(dst_head)
    dst_head.parent = dst_root
    target = KotorModel(name="target", root_node=dst_root)

    pose = AnimPose(nodes={"head": NodePose(name="head", position=(0.0, 0.0, 20.0))})

    scaled = retarget_pose(pose, source, target)
    unscaled = retarget_pose(
        pose,
        source,
        target,
        config=RetargetConfig(preserve_model_scale=False),
    )

    assert scaled.pose.nodes["head"].position[2] == pytest.approx(10.0)
    assert unscaled.pose.nodes["head"].position[2] == pytest.approx(15.0)


def test_bone_map_reports_interpolated_target_bridge_bones() -> None:
    from src.core.model_data import ModelNode
    from src.unreal.animation_retargeting import build_bone_map

    src_a = ModelNode(name="a")
    src_b = ModelNode(name="b")
    dst_root = ModelNode(name="target")
    dst_a = ModelNode(name="a")
    dst_mid = ModelNode(name="mid")
    dst_b = ModelNode(name="b")
    dst_a.parent = dst_root
    dst_mid.parent = dst_a
    dst_b.parent = dst_mid
    dst_root.children.append(dst_a)
    dst_a.children.append(dst_mid)
    dst_mid.children.append(dst_b)
    source = SimpleNamespace(name="source", all_nodes=lambda: [src_a, src_b])
    target = SimpleNamespace(name="target", all_nodes=lambda: [dst_root, dst_a, dst_mid, dst_b])

    report = build_bone_map(source, target)

    assert report.mapping == {"a": "a", "b": "b"}
    assert report.derived_target == ("mid",)
    assert "mid" not in report.missing_target


def test_retarget_pose_bridges_dense_target_chain() -> None:
    import math

    import pytest

    from src.core.animation_engine import AnimPose, NodePose
    from src.core.model_data import KotorModel, ModelNode
    from src.unreal.animation_retargeting import retarget_pose

    source = KotorModel(name="source")
    source_root = ModelNode(name="source")
    source.root_node = source_root
    source_a = ModelNode(name="a")
    source_b = ModelNode(name="b")
    source_a.parent = source_root
    source_b.parent = source_a
    source_root.children.append(source_a)
    source_a.children.append(source_b)

    target = KotorModel(name="target")
    target_root = ModelNode(name="target")
    target.root_node = target_root
    target_a = ModelNode(name="a")
    target_mid = ModelNode(name="mid")
    target_b = ModelNode(name="b")
    target_a.parent = target_root
    target_mid.parent = target_a
    target_b.parent = target_mid
    target_root.children.append(target_a)
    target_a.children.append(target_mid)
    target_mid.children.append(target_b)

    q90 = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    pose = AnimPose(nodes={
        "a": NodePose(name="a"),
        "b": NodePose(name="b", rotation=q90),
    })

    result = retarget_pose(pose, source, target)

    assert "mid" in result.pose.nodes
    assert "mid" in result.report.derived_target
    assert result.pose.nodes["mid"].rotation[2] == pytest.approx(math.sin(math.radians(22.5)))
    assert result.pose.nodes["b"].rotation[2] == pytest.approx(math.sin(math.radians(22.5)))


def test_retarget_animation_bakes_bridge_bones() -> None:
    import math

    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.unreal.animation_retargeting import retarget_animation

    source = KotorModel(name="source")
    source_root = ModelNode(name="source")
    source.root_node = source_root
    source_a = ModelNode(name="a")
    source_b = ModelNode(name="b")
    source_a.parent = source_root
    source_b.parent = source_a
    source_root.children.append(source_a)
    source_a.children.append(source_b)

    q90 = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    anim_b = ModelNode(name="b")
    anim_b.controllers = [{"type": 20, "times": [0.0, 1.0], "values": [(0.0, 0.0, 0.0, 1.0), q90]}]
    source.animations = [Animation(name="turn", length=1.0, nodes=[anim_b])]

    target = KotorModel(name="target")
    target_root = ModelNode(name="target")
    target.root_node = target_root
    target_a = ModelNode(name="a")
    target_mid = ModelNode(name="mid")
    target_b = ModelNode(name="b")
    target_a.parent = target_root
    target_mid.parent = target_a
    target_b.parent = target_mid
    target_root.children.append(target_a)
    target_a.children.append(target_mid)
    target_mid.children.append(target_b)

    baked, report = retarget_animation(source.animations[0], source, target)

    baked_names = {node.name.lower() for node in baked.nodes}
    assert "mid" in baked_names
    assert "mid" in report.derived_target


def test_gpu_vbo_splits_skin_bind_and_animated_input_space() -> None:
    import inspect

    from src.gui import gpu_renderer

    source = inspect.getsource(gpu_renderer._build_vbo_data)
    assert "apply_skin_node_transform_for_bind" in source
    assert "not is_skin or bool(apply_skin_node_transform_for_bind)" in source
    assert "elif _node_vs == 1 or is_skin" in source
