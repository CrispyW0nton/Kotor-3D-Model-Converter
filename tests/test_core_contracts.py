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
    from src.gui.gpu_renderer import _VERT_SRC

    assert "uniform float u_uv_v_flip" in _VERT_SRC
    assert "mix(in_uv.y, 1.0 - in_uv.y, u_uv_v_flip)" in _VERT_SRC


def test_gpu_ascii_multitexture_split_is_ascii_gated() -> None:
    import inspect

    from src.gui.gpu_renderer import GpuRenderer

    source = inspect.getsource(GpuRenderer._render_gpu)
    assert "ASCII/Kotor Tool MDLs use face_mats as per-face texture slots" in source
    assert "getattr(node, 'imported_ascii', False)" in source
    assert "gm.mat_slots" in source


def test_qt_gpu_viewport_uses_overlay_not_cpu_textured_fallback() -> None:
    import inspect

    from src.gui.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._draw_cpu_overlays)
    assert "_draw_mesh_textured" not in source
    assert "_draw_mesh_flat" in source
    assert "_draw_grid" in source
    assert "_draw_stats" in source


def test_qt_gpu_viewport_disables_gpu_culling_for_cpu_parity() -> None:
    import inspect

    from src.gui.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    assert "cull_faces = False" in source


def test_viewport_navigation_profiles_are_available() -> None:
    from src.gui.viewport_navigation import (
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

    from src.gui.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget._navigation_action)
    assert 'profile == "3dsmax"' in source
    assert 'profile == "blender"' in source
    assert 'profile == "maya"' in source
    assert "QtCore.Qt.AltModifier" in source


def test_qt_viewport_gpu_grid_is_native_and_xray_is_overlay_only() -> None:
    import inspect

    from src.gui.gpu_renderer import GpuRenderer
    from src.gui.qt_viewport import QtViewportWidget

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

    from src.gui.qt_animation_panel import QtAnimationsPanel

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

    from src.gui.qt_animation_panel import QtAnimationsPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtAnimationsPanel()
    labels = {button.text() for button in panel.findChildren(QtWidgets.QPushButton)}

    assert "Bake Animation" in labels
    assert "Export Binary MDL" in labels


def test_qt_main_window_builds_baked_animation_clip() -> None:
    from src.core.model_data import Animation, KotorModel, ModelNode
    from src.gui.qt_main_window import QtGhostRiggerMainWindow

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

    from src.gui.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._export_mdl_binary)

    assert "from src.core.mdl_writer import MDLBinaryWriter" in source


def test_retarget_apply_promotes_target_model_for_animation_list() -> None:
    from src.gui.qt_main_window import QtGhostRiggerMainWindow

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


def test_gpu_vbo_splits_skin_bind_and_animated_input_space() -> None:
    import inspect

    from src.gui import gpu_renderer

    source = inspect.getsource(gpu_renderer._build_vbo_data)
    assert "apply_skin_node_transform_for_bind" in source
    assert "not is_skin or bool(apply_skin_node_transform_for_bind)" in source
    assert "elif _node_vs == 1 or is_skin" in source
