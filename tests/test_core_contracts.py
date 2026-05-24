from __future__ import annotations

import inspect
import os
from types import MethodType, SimpleNamespace

import pytest


def test_vertex_space_enum_contract() -> None:
    from src.core.qt_core.geometry.vertex_space import VertexSpace

    assert list(VertexSpace) == [
        VertexSpace.NODE_LOCAL,
        VertexSpace.WORLD,
        VertexSpace.AABB_WALK,
    ]
    assert VertexSpace.NODE_LOCAL == 0
    assert VertexSpace.WORLD == 1
    assert VertexSpace.AABB_WALK == 2


def test_compute_vertex_space_aabb_walkmesh() -> None:
    from src.core.qt_core.geometry.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0x0200), None) is VertexSpace.AABB_WALK


def test_compute_vertex_space_imported_world() -> None:
    from src.core.qt_core.geometry.vertex_space import VertexSpace, compute_vertex_space

    node = SimpleNamespace(flags=0, _imported=True)
    assert compute_vertex_space(node, None) is VertexSpace.WORLD


def test_compute_vertex_space_default_node_local() -> None:
    from src.core.qt_core.geometry.vertex_space import VertexSpace, compute_vertex_space

    assert compute_vertex_space(SimpleNamespace(flags=0), None) is VertexSpace.NODE_LOCAL


def test_inner_geometry_name_matching() -> None:
    from src.core.qt_core.special.render_constants import is_inner_geometry_name

    for name in ("eyeRA", "teethU", "TongueMesh", "gumskin", "JawSkin", "eyelid"):
        assert is_inner_geometry_name(name)


def test_face_mesh_name_matching() -> None:
    from src.core.qt_core.special.render_constants import is_face_mesh_name

    for name in ("head", "Face_LOD0", "fchead01", "skullcap"):
        assert is_face_mesh_name(name)


def test_inner_geometry_does_not_match_non_inner_names() -> None:
    from src.core.qt_core.special.render_constants import is_inner_geometry_name

    for name in ("headhook", "model_root", "rootdummy", "random_mesh", ""):
        assert not is_inner_geometry_name(name)


def test_read_mdl_safe_importable_and_callable() -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    assert callable(read_mdl_safe)


def test_pykotor_mdl_binary_fixes_are_idempotent() -> None:
    from src.core.qt_core.game.pykotor_mdl_io_fix import ensure_pykotor_mdl_binary_fixes

    ensure_pykotor_mdl_binary_fixes()
    ensure_pykotor_mdl_binary_fixes()


def test_ascii_mdl_nodes_keep_imported_uv_orientation() -> None:
    from src.core.qt_core.mdl.mdl_parser import MDLAsciiParser

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
    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer

    source = inspect.getsource(GpuRenderer._render_gpu)
    assert "ASCII/Kotor Tool MDLs use face_mats as per-face texture slots" in source
    assert "getattr(node, 'imported_ascii', False)" in source
    assert "gm.mat_slots" in source


def test_viewport_render_loop_is_gpu_only() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    render_now = inspect.getsource(QtViewportWidget._render_now)
    render_frame = inspect.getsource(QtViewportWidget._render_frame)
    badge = inspect.getsource(QtViewportWidget._set_renderer_badge)
    thumbnail = inspect.getsource(QtViewportWidget._render_neutral_pose_thumbnail)
    gpu_render = inspect.getsource(GpuRenderer.render)
    cpu_hook = inspect.getsource(GpuRenderer._render_cpu)

    viewport_sources = "\n".join([render_now, render_frame, badge, thumbnail])
    assert "_use_gpu = False" not in viewport_sources
    assert 'setText("CPU' not in viewport_sources
    assert "self._renderer.render(" not in viewport_sources
    assert "_draw_cpu_overlays(" not in render_frame
    assert "_draw_performance_overlay(" not in render_now
    assert "_render_cpu(" not in gpu_render
    assert "backend'] = 'cpu'" not in gpu_render
    assert "FrameRenderer" not in cpu_hook
    assert "return None" in cpu_hook


def test_add_model_to_scene_dialog_stays_compact_under_layout_apply() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.dialogs.add_model_to_scene_dialog import AddModelToSceneDialog
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = AddModelToSceneDialog("K2:c_drdmktwo")
    dialog.apply_ghost_layout(SimpleNamespace(dialog_width=1650))

    source = inspect.getsource(QtGhostRiggerMainWindow._choose_model_import_action)
    assert "apply_current_layout(dialog)" not in source
    assert "apply_current_theme(dialog)" not in source
    assert "dialog.apply_ghost_theme(active_theme)" in source
    assert dialog.width() <= AddModelToSceneDialog.MAX_WIDTH
    assert dialog.maximumWidth() == AddModelToSceneDialog.MAX_WIDTH
    assert dialog.minimumWidth() == AddModelToSceneDialog.MAX_WIDTH


def test_qt_gpu_viewport_uses_overlay_not_cpu_textured_fallback() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    frame_source = inspect.getsource(QtViewportWidget._render_frame)
    source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)
    legacy_source = inspect.getsource(QtViewportWidget._draw_cpu_overlays)

    assert "_draw_gpu_viewport_overlays" in frame_source
    assert "_draw_performance_overlay" in frame_source
    assert "self._renderer.render(" not in frame_source
    assert "_draw_mesh_textured" not in source
    assert "_draw_mesh_flat" not in source
    assert "self._xray_mode" in source
    assert "_draw_grid" in source
    assert "_draw_stats" in source
    assert "_draw_transform_gizmo" in source
    assert "_draw_axes" in source
    assert "return self._draw_gpu_viewport_overlays" in legacy_source


def test_qt_gpu_viewport_keeps_gpu_for_wire_and_texture_off_modes() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    frame_source = inspect.getsource(QtViewportWidget._render_frame)
    gpu_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert "gpu_can_match_mode" not in frame_source
    assert "self._render_gpu_frame(w, h)" in frame_source
    assert "self._renderer.render(" not in frame_source
    assert "and self._renderer.show_texture" not in frame_source
    assert "show_texture = bool(self._renderer.show_texture)" in gpu_source
    assert "show_wireframe = bool(self._renderer.show_wireframe)" in gpu_source


def test_qt_viewport_grid_toggle_controls_cpu_and_gpu_paths() -> None:
    import inspect

    from src.gui.qt_lib.rendering.viewport_core import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    frame_grid_source = inspect.getsource(FrameRenderer._draw_grid)
    viewport_build_source = inspect.getsource(QtViewportWidget._build)
    toggle_source = inspect.getsource(QtViewportWidget.toggle_grid)
    gpu_source = inspect.getsource(QtViewportWidget._render_gpu_frame)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions) + inspect.getsource(QtGhostRiggerMainWindow._build_menu)

    assert 'getattr(self, "show_grid", True)' in frame_grid_source
    assert "self.grid_button" in viewport_build_source
    assert "self._renderer.show_grid = self.grid_button.isChecked()" in viewport_build_source
    assert "self._gpu_renderer.show_grid = enabled" in toggle_source
    assert 'show_grid = bool(getattr(self._renderer, "show_grid", True))' in gpu_source
    assert "Toggle Grid" in menu_source
    assert 'setShortcut("Alt+G")' in menu_source
    assert '"grid_button"' in menu_source


def test_qt_viewport_performance_overlay_stacks_above_stats_badge() -> None:
    import inspect

    from src.gui.qt_lib.rendering.viewport_core import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    stats_source = inspect.getsource(FrameRenderer._draw_stats)
    perf_source = inspect.getsource(QtViewportWidget._draw_performance_overlay)

    assert "max(12, H - 28)" in stats_source
    assert "h - 50" in perf_source
    assert "_draw_hud_pill" in perf_source


def test_qt_gpu_viewport_resets_render_targets_on_model_load() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    gpu_source = inspect.getsource(GpuRenderer.reset_framebuffers)
    load_source = inspect.getsource(QtViewportWidget.load_model)

    assert "self._fbo = None" in gpu_source
    assert "self._fbo_simple = None" in gpu_source
    assert "reset_framebuffers()" in load_source
    assert "self._request_render(fast=True)" in load_source


def test_gpu_renderer_supports_texture_off_and_wireframe_modes() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)

    assert "self.show_texture: bool = True" in init_source
    assert "self.show_solid: bool = True" in init_source
    assert "self.wire_color: tuple[float, float, float] = (0.18, 0.62, 0.95)" in init_source
    assert "self.show_diffuse_map: bool = True" in init_source
    assert "self.show_lightmap_map: bool = False" in init_source
    assert "self.show_environment_map: bool = True" in init_source
    assert "self.show_specular_map: bool = True" in init_source
    assert "self.lightmap_intensity: float = 0.55" in init_source
    assert "self.lightmap_mode: str = \"disabled\"" in init_source
    assert "self.show_light_gizmos: bool = True" in init_source
    assert "_texture_allowed = bool(self.show_texture and self.show_diffuse_map)" in render_source
    assert "bool(self.show_lightmap_map)" in render_source
    assert "bool(self.show_environment_map)" in render_source
    assert "bool(self.show_specular_map)" in render_source
    assert "_draw_light_gizmos" in render_source
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
    assert "_detail_texture_allowed = bool(self.show_texture and _render_mode_int == 0)" in render_source
    assert "u_bump_tex" in _FRAG_SRC
    assert "u_has_bump" in _FRAG_SRC
    assert "u_lightmap_intensity" in _FRAG_SRC
    assert "u_lightmap_mode" in _FRAG_SRC
    assert "if _gpu_is_module and _render_mode_int in (1, 2)" in render_source
    assert "render_mode = str(getattr(self._renderer" in viewport_source
    assert "lightmap_intensity = float(getattr(self._renderer" in viewport_source
    assert "lightmap_mode = str(getattr(self._renderer" in viewport_source
    assert "selected_node = getattr(self._renderer" in viewport_source
    assert "selected_nodes = list(getattr(self, \"_selected_meshes\"" in viewport_source
    assert "_texture_allowed = bool(self.show_texture and self.show_diffuse_map)" in render_source


def test_gpu_static_mesh_prebuild_uses_ram_and_chunked_uploads() -> None:
    import inspect

    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
    from src.gui.qt_lib.rendering import gpu_renderer
    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer
    from src.gui.qt_lib.rendering.viewport_core import FrameRenderer
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    node = ModelNode(
        name="tri",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        faces=[(0, 1, 2)],
        texture="test",
    )
    model = KotorModel(name="prebuild", root_node=node)

    assert gpu_renderer.prebuild_static_gpu_mesh_data(model) == 1
    entry = getattr(node, "_gr_gpu_prebuilt_static_mesh")
    assert entry["model_id"] == id(model)
    assert entry["vdata"].shape[0] == 3
    assert getattr(model, "_gr_bounds_prepared") is True
    assert getattr(model, "_gr_render_bounds") == ((0.0, 0.0, 0.0), (1.0, 1.0, 0.0))
    assert gpu_renderer.clear_prebuilt_static_gpu_model_data(model) == 1
    assert not hasattr(node, "_gr_gpu_prebuilt_static_mesh")

    init_source = inspect.getsource(GpuRenderer.__init__)
    render_source = inspect.getsource(GpuRenderer._render_gpu)
    renderer_set_model_source = inspect.getsource(FrameRenderer.set_model)
    load_source = inspect.getsource(QtViewportWidget.load_model)
    viewport_source = inspect.getsource(QtViewportWidget._render_gpu_frame)

    assert "self.max_new_mesh_uploads_per_frame: int = 64" in init_source
    assert "self.deferred_mesh_uploads = True" in render_source
    assert "_prebuilt_static_gpu_mesh_data" in render_source
    assert "prepared_bounds = getattr(m, \"_gr_render_bounds\", None)" in renderer_set_model_source
    assert "getattr(m, \"_gr_defer_txi_metadata\", False)" in renderer_set_model_source
    assert "clear_prebuilt_static_gpu_model_data(old_model)" in load_source
    assert "self._gpu_renderer.clear_caches()" in load_source
    assert "if not getattr(model, \"_gr_bounds_prepared\", False)" in load_source
    assert "self._start_deferred_txi_metadata(model)" in load_source
    assert "gpuUploadProgress.emit" in viewport_source
    assert "_request_render(fast=True)" in viewport_source


def test_kmax_scene_composite_preserves_authored_root_name_for_animation_skinning() -> None:
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode, NodeFlags
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    root = ModelNode(name="N_Bith", flags=int(NodeFlags.HEADER), position=(9.0, 8.0, 7.0))
    head_bone = ModelNode(name="head_g", flags=int(NodeFlags.HEADER))
    skin = ModelNode(name="Head", flags=int(NodeFlags.HEADER) | int(NodeFlags.MESH) | int(NodeFlags.SKIN))
    skin.bone_map = ["N_Bith", "head_g"]
    skin.qbone_list = [(1.0, 0.0, 0.0, 0.0)] * 3
    skin.tbone_list = [(0.0, 0.0, 0.0)] * 3
    root.children.append(head_bone)
    head_bone.parent = root
    root.children.append(skin)
    skin.parent = root
    model = KotorModel(name="N_Bith", root_node=root)

    fake_viewport = SimpleNamespace()
    fake_viewport._tag_scene_object_nodes = MethodType(QtViewportWidget._tag_scene_object_nodes, fake_viewport)
    fake_viewport._tag_scene_source_indices = MethodType(QtViewportWidget._tag_scene_source_indices, fake_viewport)
    fake_viewport._euler_degrees_to_quat = QtViewportWidget._euler_degrees_to_quat

    instance = SimpleNamespace(
        id="scene-object-1",
        name="Bith Actor",
        visible=True,
        metadata={"_runtime_model": model},
        transform=SimpleNamespace(position=(1.0, 2.0, 3.0), rotation=(0.0, 0.0, 0.0)),
    )

    composite = QtViewportWidget._build_scene_composite_model(fake_viewport, [instance], "Untitled Scene")
    placed_root = composite.root_node.children[0]
    placed_skin = placed_root.children[1]

    assert placed_root.name == "N_Bith"
    assert placed_root.position == (1.0, 2.0, 3.0)
    assert getattr(placed_root, "_gr_scene_source_position") == (9.0, 8.0, 7.0)
    assert getattr(placed_root, "_gr_scene_gpu_transform") is True
    assert getattr(placed_root, "_gr_scene_object_name") == "Bith Actor"
    assert placed_skin.bone_map[0] == placed_root.name
    assert getattr(placed_skin, "_gr_scene_object_id") == "scene-object-1"

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(composite)
    assert uploader._name_to_dfs_index["n_bith"] == 0
    assert uploader._name_to_dfs_index["head_g"] == 1
    assert uploader._name_to_dfs_index["head"] == 2
    assert uploader._model_node_count == 3
    uploader.compute_skin_node_palette(placed_skin, SimpleNamespace(nodes={}))
    assert uploader._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"


def test_kmax_scene_gpu_transform_uses_authored_vbo_basis() -> None:
    from src.gui.rendering.gpu_renderer import _scene_authored_world_transform, _scene_gpu_model_matrix

    child = SimpleNamespace(
        position=(2.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=None,
    )
    root = SimpleNamespace(
        position=(100.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        parent=None,
        _gr_scale=(3.0, 3.0, 3.0),
        _gr_scene_object_root=True,
        _gr_scene_gpu_transform=True,
        _gr_scene_source_position=(9.0, 8.0, 7.0),
        _gr_scene_source_rotation=(0.0, 0.0, 0.0, 1.0),
    )
    child.parent = root

    authored_pos, _authored_rot = _scene_authored_world_transform(child)
    scene_mat = _scene_gpu_model_matrix(child)

    assert authored_pos == pytest.approx((11.0, 8.0, 7.0))
    assert scene_mat[0, 3] == pytest.approx(100.0)
    assert scene_mat[0, 0] == pytest.approx(3.0)


def test_kmax_scene_reload_preserves_selected_object_for_pivot_tools() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    load_model_source = inspect.getsource(QtViewportWidget.load_model)
    load_scene_source = inspect.getsource(QtViewportWidget.load_scene_instances)

    assert 'getattr(root_node, "_gr_scene_composite_root", False)' in load_model_source
    assert "selected_id =" in load_scene_source
    assert "self.load_model(composite" in load_scene_source
    assert "self.select_scene_object(selected_id)" in load_scene_source


def test_transform_cache_evict_clears_frame_and_gpu_child_caches() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    child = SimpleNamespace(children=[])
    setattr(child, "_gr_gpu_prebuilt_static_mesh", {"model_id": 1, "skin_bind_transform": False})
    parent = SimpleNamespace(children=[child])

    invalidated = []
    viewport = SimpleNamespace(
        _renderer=SimpleNamespace(
            _wt_cache={id(parent): object(), id(child): object()},
            _frame_view=object(),
            _frame_verts_cache={id(child): [(0.0, 0.0, 0.0)]},
            _frame_norms_cache={id(child): [(0.0, 0.0, 1.0)]},
        ),
        _gpu_renderer=SimpleNamespace(invalidate_node=lambda node: invalidated.append(node)),
    )

    QtViewportWidget._evict_transform_cache(viewport, parent)

    assert not hasattr(child, "_gr_gpu_prebuilt_static_mesh")
    assert viewport._renderer._wt_cache == {}
    assert viewport._renderer._frame_view is None
    assert viewport._renderer._frame_verts_cache == {}
    assert viewport._renderer._frame_norms_cache == {}
    assert invalidated == [parent, child]


def test_model_load_worker_uses_single_read_and_gpu_prebuild() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import (
        ModelLoadWorker,
        QtGhostRiggerMainWindow,
        QtProgressToast,
        ResourceModelLoadWorker,
    )

    file_source = inspect.getsource(ModelLoadWorker.run)
    toast_source = inspect.getsource(QtProgressToast)
    window_source = inspect.getsource(QtGhostRiggerMainWindow)
    get_resource_manager_source = inspect.getsource(QtGhostRiggerMainWindow._get_resource_manager)
    resource_source = inspect.getsource(ResourceModelLoadWorker.run)
    viewport_preload_source = inspect.getsource(__import__(
        "src.gui.qt_lib.viewports.qt_viewport",
        fromlist=["QtViewportWidget"],
    ).QtViewportWidget._preload_gpu_textures)

    assert "progress = QtCore.Signal(str, int, int)" in inspect.getsource(ModelLoadWorker)
    assert "progress = QtCore.Signal(str, int, int)" in inspect.getsource(ResourceModelLoadWorker)
    assert "raw = path.read_bytes()" in file_source
    assert 'raw.decode("utf-8", errors="replace")' in file_source
    assert "load_model_from_bytes" in file_source
    assert "load_model_from_file" not in file_source
    assert "self.progress.emit" in file_source
    assert "_prebuild_gpu_mesh_data_for_model(model)" in file_source
    assert "self.progress.emit" in resource_source
    assert "_prebuild_gpu_mesh_data_for_model(model)" in resource_source
    assert "def update_progress" in toast_source
    assert "worker.progress.connect(self._on_model_load_progress)" in window_source
    assert "gpuUploadProgress.connect(self._on_viewport_gpu_upload_progress)" in window_source
    assert "existing is not None" in get_resource_manager_source
    assert "_resource_manager_dirs" in get_resource_manager_source
    assert "tex_cache.get" not in viewport_preload_source


def test_qt_realistic_texture_prewarm_loads_detail_textures_without_paint_stall() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    node = SimpleNamespace(
        vertices=[(0.0, 0.0, 0.0)],
        texture_clean="LMA_wall01.tga",
        texture="LMA_wall01",
        lightmap="LMA_wall01_lm",
        bump_map="mdl_bump",
        txi_envmaptexture="CM_Baremetal",
        txi_specularcolour="metal_spec",
        txi_bumpmaptexture="stone_bump",
        texture_names=["trim01", "NULL", "****", "None", "lma_wall01"],
    )
    helper = SimpleNamespace(
        vertices=[],
        texture_clean="should_not_load",
        lightmap="should_not_load_lm",
    )
    model = SimpleNamespace(
        all_nodes=lambda: [node, helper],
        mesh_nodes=lambda: [],
    )

    names = QtViewportWidget._texture_names_for_prewarm(model)

    assert names == [
        "lma_wall01",
        "lma_wall01_lm",
        "mdl_bump",
        "cm_baremetal",
        "metal_spec",
        "stone_bump",
        "trim01",
    ]

    prewarm_source = inspect.getsource(QtViewportWidget._prewarm_textures)
    deferred_txi_source = inspect.getsource(QtViewportWidget._on_deferred_txi_finished)

    assert "_texture_names_for_prewarm(model)" in prewarm_source
    assert "_texturePrewarmFinished.emit(model_id)" in prewarm_source
    assert "time_module.sleep(0.35)" not in prewarm_source
    assert "self._prewarm_textures(self.model)" in deferred_txi_source


def test_gpu_auto_clamp_diffuse_is_disabled_for_module_geometry() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.rendering.gpu_renderer import _should_auto_clamp_diffuse

    atlas_like_node = SimpleNamespace(
        txi_clamp_s=False,
        txi_clamp_t=False,
        animate_uv=False,
        txi_proceduretype="",
        txi_blending=0,
        uvs=[(0.1, 0.2), (0.9, 0.2), (0.9, 0.8), (0.1, 0.8)],
    )

    assert _should_auto_clamp_diffuse(atlas_like_node, is_module=False) is True
    assert _should_auto_clamp_diffuse(atlas_like_node, is_module=True) is False


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
        faces=[(0, 0, 0)],
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


def test_module_mesh_properties_panel_splits_meshes_nulls_and_walkmeshes() -> None:
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
    null_mesh = SimpleNamespace(
        name="external_null",
        is_mesh=True,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="NULL",
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [regular_mesh, null_mesh],
        all_nodes=lambda: [regular_mesh, null_mesh, grey_geometry],
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
    null_names = [
        panel.module_null_mesh_tree.topLevelItem(index).text(0)
        for index in range(panel.module_null_mesh_tree.topLevelItemCount())
    ]
    assert mesh_names == ["regular_mesh"]
    assert null_names == ["external_null"]
    assert walkmesh_names == ["walkmesh_12"]
    assert panel.module_browser_tabs.tabText(1) == "NULL Meshes"
    assert panel.module_browser_tabs.tabText(2) == "Walkmeshes"


def test_module_mesh_properties_panel_lists_coloaded_walkmesh_overlay_nodes() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()
    overlay_node = SimpleNamespace(
        name="m01aa_01a_overlay",
        flags=0x0200,
        vertex_space=1,
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        faces=[(0, 1, 2)],
        texture="walkmesh",
        _gr_walkmesh_overlay_proxy=True,
    )
    model = SimpleNamespace(
        name="m01aa_01a",
        game_version="K1",
        supermodel="NULL",
        classification="tile",
        animations=[],
        mesh_nodes=lambda: [],
        all_nodes=lambda: [],
        bone_nodes=lambda: [],
        texture_list=lambda: [],
        _gr_extra_module_mesh_nodes=[overlay_node],
    )

    selected_batches = []
    panel.moduleMeshesSelected.connect(selected_batches.append)
    panel.show_model(model)

    assert panel.module_walkmesh_tree.topLevelItemCount() == 1
    assert panel.module_walkmesh_tree.topLevelItem(0).text(0) == "m01aa_01a_overlay"
    panel.module_walkmesh_tree.setCurrentItem(panel.module_walkmesh_tree.topLevelItem(0))
    assert selected_batches[-1] == [overlay_node]


def test_coloaded_walkmesh_overlay_aligns_to_existing_model_walkmesh_bounds() -> None:
    from src.gui.qt_lib.windows.qt_main_window import (
        _walkmesh_overlay_node_from_wok,
        _walkmesh_overlay_offset_for_model,
    )

    face = SimpleNamespace(v1=0, v2=1, v3=2, surface=7)
    wok = SimpleNamespace(
        verts=[(100.0, 200.0, 5.0), (110.0, 200.0, 5.0), (100.0, 210.0, 5.0)],
        faces=[face],
    )
    reference_walkmesh = SimpleNamespace(
        name="walkmesh_12",
        flags=0x0200,
        vertex_space=2,
        vertices=[(10.0, 20.0, 1.0), (20.0, 20.0, 1.0), (10.0, 30.0, 1.0)],
        faces=[(0, 1, 2)],
    )
    model = SimpleNamespace(
        all_nodes=lambda: [reference_walkmesh],
        render_bounds=lambda: ((10.0, 20.0, 1.0), (20.0, 30.0, 1.0)),
    )

    offset = _walkmesh_overlay_offset_for_model(model, wok)
    proxy = _walkmesh_overlay_node_from_wok(wok, "K1:m01aa_01a.wok", offset)

    assert offset == (-90.0, -180.0, -4.0)
    assert proxy.name == "m01aa_01a_overlay"
    assert proxy.vertices == reference_walkmesh.vertices
    assert proxy.faces == [(0, 1, 2)]
    assert proxy.face_mats == [7]
    assert proxy._gr_walkmesh_overlay_proxy is True


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


def test_qt_viewport_mesh_pick_requires_real_triangle_and_hover_outline() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget)
    pick_source = inspect.getsource(QtViewportWidget._mesh_hit_test_detail)
    release_source = inspect.getsource(QtViewportWidget._release_lmb)
    overlay_source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)

    assert "self._hovered_mesh_node = None" in source
    assert "_update_mesh_hover(event)" in source
    assert "_draw_hovered_mesh_outline(draw, w, h)" in overlay_source
    assert "_ray_triangle_intersection" in pick_source
    assert "area + dist2" not in pick_source
    assert "_hit_test_model_bounds" not in release_source

    hit = QtViewportWidget._ray_triangle_intersection(
        (0.25, 0.25, 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    miss = QtViewportWidget._ray_triangle_intersection(
        (1.25, 1.25, 1.0),
        (0.0, 0.0, -1.0),
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
    )
    assert hit == 1.0
    assert miss is None


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


def test_transform_gizmo_controller_applies_translate_rotate_scale_and_cancel() -> None:
    from types import SimpleNamespace

    import pytest

    from src.gui.qt_lib.gizmo.gizmo_mode import GizmoMode
    from src.gui.qt_lib.gizmo.transform_controller import TransformController
    from src.gui.qt_lib.gizmo.transform_gizmo import TransformGizmo

    class _Camera:
        fov = 45.0

        def _view_matrix(self):
            return (
                (1.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (0.0, -1.0, 0.0),
                (0.0, 10.0, 0.0),
            )

    camera = _Camera()
    node = SimpleNamespace(
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(1.0, 2.0, 3.0)],
        compute_bounds=lambda: None,
    )
    controller = TransformController()

    controller.begin_drag(node, GizmoMode.TRANSLATE, "TRANSLATE_X", (100, 100), camera, depth=5.0)
    controller.drag((120, 100), camera, 500)
    assert node.position[0] > 0.0
    controller.cancel()
    assert node.position == pytest.approx((0.0, 0.0, 0.0))

    controller.begin_drag(node, GizmoMode.ROTATE, "ROTATE_Z", (100, 100), camera, depth=5.0)
    controller.drag((140, 100), camera, 500)
    assert node.rotation[2] < 0.0
    before, after, changed = controller.end_drag()
    assert changed is node
    assert before is not None and after is not None
    assert after.rotation != pytest.approx(before.rotation)

    controller.begin_drag(node, GizmoMode.SCALE, "SCALE_UNIFORM", (100, 100), camera, depth=5.0)
    controller.drag((120, 90), camera, 500)
    assert node.vertices[0][0] > 1.0
    assert node.vertices[0][1] > 2.0

    gizmo = TransformGizmo()
    assert gizmo.mode == GizmoMode.TRANSLATE
    assert gizmo.cycle_mode() == GizmoMode.ROTATE
    assert gizmo.cycle_mode() == GizmoMode.SCALE
    assert gizmo.cycle_mode() == GizmoMode.TRANSLATE


def test_gizmo_picker_hits_projected_rotation_polylines() -> None:
    from src.gui.qt_lib.gizmo.gizmo_picker import GizmoPicker

    picker = GizmoPicker()
    handle = {
        "name": "ROTATE_Z",
        "kind": "polyline",
        "points": [(10, 10), (50, 10), (50, 50)],
        "radius": 8,
    }

    assert picker.hit_test((30, 14), [handle]) == "ROTATE_Z"
    assert picker.hit_test((30, 30), [handle]) is None


def test_gizmo_picker_prioritizes_uniform_scale_center_handle() -> None:
    from src.gui.qt_lib.gizmo.gizmo_picker import GizmoPicker

    picker = GizmoPicker()
    handles = [
        {"name": "SCALE_X", "kind": "segment", "start": (50, 50), "end": (100, 50), "radius": 10},
        {"name": "SCALE_UNIFORM", "kind": "point", "pos": (50, 50), "radius": 14, "priority": 10},
    ]

    assert picker.hit_test((50, 50), handles) == "SCALE_UNIFORM"


def test_qt_viewport_selection_does_not_auto_recenter_but_z_frames_selection() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import pytest
    from PySide6 import QtWidgets

    from src.core.qt_core.geometry.model_data import ModelNode
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    viewport = QtViewportWidget()
    viewport.camera.target = [0.0, 0.0, 0.0]
    viewport.camera.distance = 10.0
    viewport.camera.azimuth = 90.0
    viewport.camera.elevation = 0.0
    old_eye = viewport.camera.eye()

    mesh = ModelNode(
        name="selected_face",
        vertices=[(10.0, 0.0, 0.0), (12.0, 0.0, 0.0), (10.0, 2.0, 0.0)],
        faces=[(0, 1, 2)],
    )
    face_bounds = ((10.0, 0.0, 0.0), (12.0, 2.0, 0.0))

    viewport.set_selected_node(mesh, orbit_bounds=face_bounds)

    assert viewport.camera.target == pytest.approx([0.0, 0.0, 0.0])
    assert viewport.camera.eye() == pytest.approx(old_eye)

    viewport.camera.target = [0.0, 0.0, 0.0]
    viewport.frame_selection_or_all()

    assert viewport.camera.target == pytest.approx([11.0, 1.0, 0.0])


def test_qt_lighting_panel_editor_refresh_preserves_selected_light() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    first = SimpleNamespace(
        name="AuroraLight001",
        is_light=True,
        light_kind="point",
        light_radius=1.5,
        light_enabled=True,
        light_multiplier=1.0,
        light_cone_degrees=45.0,
        light_area_size=1.0,
        light_ambient_only=False,
    )
    second = SimpleNamespace(
        name="AuroraLight223",
        is_light=True,
        light_kind="point",
        light_radius=11.75,
        light_enabled=True,
        light_multiplier=1.0,
        light_cone_degrees=45.0,
        light_area_size=1.0,
        light_ambient_only=False,
    )
    panel = QtLightingPanel()
    panel.set_model(SimpleNamespace(all_nodes=lambda: [first, second]))
    panel.tree.setCurrentItem(panel.tree.topLevelItem(1))

    panel.radius_spin.setValue(12.25)

    assert panel._selected is second
    assert second.light_radius == 12.25
    assert first.light_radius == 1.5
    assert panel.tree.currentItem().data(0, QtCore.Qt.UserRole) is second


def test_qt_viewport_can_pick_light_gizmos() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    light = SimpleNamespace(
        name="AuroraLight223",
        is_light=True,
        position=(1.0, 2.0, 3.0),
    )
    mesh = SimpleNamespace(
        name="room_mesh",
        is_light=False,
        position=(0.0, 0.0, 0.0),
    )
    viewport = QtViewportWidget()
    viewport.model = SimpleNamespace(all_nodes=lambda: [mesh, light])
    viewport._renderer._node_world_transform = lambda node: (node.position, (0.0, 0.0, 0.0, 1.0), True)
    viewport._renderer._proj = lambda _x, _y, _z, _w, _h: (100, 120, 5.0)

    assert viewport._light_hit_test(104, 123) is light
    assert viewport._light_hit_test(140, 160) is None


def test_qt_lighting_panel_select_light_syncs_from_viewport_without_emitting() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.panels.qt_lighting_panel import QtLightingPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    first = SimpleNamespace(name="AuroraLight001", is_light=True, light_kind="point", light_radius=1.5)
    second = SimpleNamespace(name="AuroraLight223", is_light=True, light_kind="point", light_radius=11.75)
    panel = QtLightingPanel()
    emitted = []
    panel.lightSelected.connect(emitted.append)
    panel.set_model(SimpleNamespace(all_nodes=lambda: [first, second]))
    emitted.clear()

    panel.select_light(second)

    assert emitted == []
    assert panel._selected is second
    assert panel.tree.currentItem().data(0, QtCore.Qt.UserRole) is second
    assert panel.radius_spin.value() == 11.75

    panel.select_light(None)

    assert emitted == []
    assert panel._selected is None
    assert panel.tree.selectedItems() == []


def test_cinematic_camera_model_links_focal_length_and_fov() -> None:
    import math
    import pytest

    from src.gui.camera.camera_model import GhostRiggerCamera

    camera = GhostRiggerCamera()
    camera.set_focal_length(85.0)

    assert camera.focal_length_mm == pytest.approx(85.0)
    assert camera.field_of_view_degrees < 30.0

    camera.set_field_of_view(60.0)

    assert camera.field_of_view_degrees == pytest.approx(60.0)
    assert camera.focal_length_mm == pytest.approx(36.0 / (2.0 * math.tan(math.radians(60.0) * 0.5)))


def test_camera_manager_serializes_scene_cameras_and_active_camera() -> None:
    from types import SimpleNamespace
    from src.gui.camera.camera_manager import CameraManager

    model = SimpleNamespace(name="danm13aa", _base_nodes=[])
    model.all_nodes = lambda: list(model._base_nodes)
    manager = CameraManager()
    manager.set_model(model)
    camera = manager.create_camera(camera_type="Cinematic Camera")
    manager.set_active_camera(camera.id)
    manager.select_camera(camera.id)

    payload = manager.serialize()

    assert payload["active_camera_id"] == camera.id
    assert payload["cameras"][0]["name"] == "Camera001"
    assert getattr(model, "_gr_camera_state")["active_camera_id"] == camera.id
    assert any(getattr(node, "is_camera", False) for node in model.all_nodes())

    restored = CameraManager()
    restored.set_model(model)

    assert restored.get_active_camera().id == camera.id
    assert restored.get_all_cameras()[0].name == "Camera001"


def test_render_output_builds_incrementing_camera_paths(tmp_path) -> None:
    from pathlib import Path

    from src.gui.camera.camera_render_settings import RenderSettings
    from src.gui.camera.render_output import RenderOutput

    settings = RenderSettings(output_directory=str(tmp_path), output_format="JPG", filename_prefix="")
    output = RenderOutput()
    first = output.build_output_path("Camera001", settings, module_name="danm13aa")
    Path(first).write_text("existing", encoding="utf-8")
    second = output.build_output_path("Camera001", settings, module_name="danm13aa")

    assert Path(first).name == "danm13aa_Camera001_0001.jpg"
    assert Path(second).name == "danm13aa_Camera001_0002.jpg"


def test_qt_viewport_exposes_cinematic_camera_workflow_methods() -> None:
    import inspect

    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    source = inspect.getsource(QtViewportWidget)

    assert "self.camera_manager = CameraManager()" in source
    assert "def switch_to_camera" in source
    assert "def switch_to_perspective" in source
    assert "def update_view_from_camera" in source
    assert "def update_camera_from_view" in source
    assert "def render_still_frame" in source
    assert "_camera_hit_test" in source
    assert "_draw_active_camera_overlays" in source


def test_camera_letterbox_render_burns_opaque_black_bars() -> None:
    from PIL import Image, ImageDraw

    from src.gui.camera.camera_model import GhostRiggerCamera
    from src.gui.camera.camera_overlays import CameraOverlays

    camera = GhostRiggerCamera(show_letterbox=True, letterbox_ratio=4.0)
    image = Image.new("RGBA", (100, 100), (64, 64, 64, 255))
    overlays = CameraOverlays()
    draw = ImageDraw.Draw(image, "RGBA")

    overlays.draw_letterbox(draw, overlays.active_frame_rect(camera, 100, 100), 100, 100, opaque=True)

    assert image.getpixel((50, 5)) == (0, 0, 0, 255)


def test_still_frame_renderer_suppresses_viewport_camera_overlays() -> None:
    from types import SimpleNamespace

    from PIL import Image

    from src.gui.camera.camera_model import GhostRiggerCamera
    from src.gui.camera.camera_render_settings import RenderSettings
    from src.gui.camera.frame_renderer import FrameRenderer

    calls = []
    viewport = SimpleNamespace(
        _renderer=SimpleNamespace(show_gimbal=True, show_grid=True, show_light_gizmos=True),
        _gpu_renderer=SimpleNamespace(show_grid=True, show_light_gizmos=True),
        _camera_helper_renderer=SimpleNamespace(show_camera_helpers=True),
        _render_suppress_camera_overlays=False,
    )

    def _render_frame(width: int, height: int):
        calls.append(bool(viewport._render_suppress_camera_overlays))
        return Image.new("RGBA", (width, height), (32, 32, 32, 255))

    viewport._render_frame = _render_frame
    renderer = FrameRenderer(viewport)
    settings = RenderSettings(
        resolution_source="custom",
        resolution_width=32,
        resolution_height=24,
        include_letterbox=False,
        include_safe_frame=False,
        include_camera_guides=False,
        include_grid=False,
        include_helpers=False,
    )

    image = renderer.render_current_frame(settings, GhostRiggerCamera())

    assert image.size == (32, 24)
    assert calls == [True]
    assert viewport._render_suppress_camera_overlays is False
    assert viewport._renderer.show_grid is True
    assert viewport._camera_helper_renderer.show_camera_helpers is True


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
    assert "Alt+G: Toggle grid" in VIEWPORT_NAVIGATION_HELP
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
    overlay_source = inspect.getsource(QtViewportWidget._draw_gpu_viewport_overlays)
    assert "if self._xray_mode" in overlay_source
    assert "not gpu_base" not in overlay_source
    event_source = inspect.getsource(QtViewportWidget.eventFilter)
    assert "QtCore.Qt.Key_G" in event_source
    assert "self.grid_button.click()" in event_source
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


def test_main_window_exposes_module_meshes_as_detachable_dock() -> None:
    import inspect
    from pathlib import Path

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)
    refresh_source = inspect.getsource(QtGhostRiggerMainWindow._refresh_all)

    assert "self.properties_panel = QtPropertiesPanel(self, module_browser_enabled=False)" in layout_source
    assert "self.module_geometry_panel = QtPropertiesPanel(self)" in layout_source
    assert "self.module_geometry_panel.set_module_browser_only(True)" in layout_source
    assert '"module_meshes"' in layout_source
    assert "self.module_meshes_panel_action" in actions_source
    assert 'self._icon("module_meshes")' in actions_source
    assert "modules_menu.addAction(self.module_meshes_panel_action)" in menu_source
    assert "self.module_geometry_panel.show_model(model)" in refresh_source
    assert (Path("src/gui/icons/module_meshes.svg")).exists()
    assert hasattr(QtPropertiesPanel, "set_module_browser_only")


def test_main_window_exposes_adjust_pivot_in_modules_menu() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._build_menu)

    assert "self.adjust_pivot_panel = AdjustPivotPanel(self)" in layout_source
    assert '"adjust_pivot"' in layout_source
    assert "self.adjust_pivot_panel_action" in actions_source
    assert 'self._show_workspace_dock("adjust_pivot")' in actions_source
    assert "modules_menu.addAction(self.adjust_pivot_panel_action)" in menu_source


def test_adjust_pivot_mode_buttons_are_persistent_toggles() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.adjust_pivot_panel import AdjustPivotPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = AdjustPivotPanel()
    try:
        panel.set_selection_state(1, locked=False, hierarchy_available=True)
        emitted = []
        panel.pivotModeChanged.connect(emitted.append)

        pivot_button = panel._mode_buttons["affect_pivot_only"]
        object_button = panel._mode_buttons["affect_object_only"]
        hierarchy_button = panel._mode_buttons["affect_hierarchy_only"]

        pivot_button.click()
        assert pivot_button.isChecked()
        assert not object_button.isChecked()
        assert emitted[-1] == "affect_pivot_only"

        hierarchy_button.click()
        assert hierarchy_button.isChecked()
        assert not pivot_button.isChecked()
        assert emitted[-1] == "affect_hierarchy_only"
    finally:
        panel.close()


def test_adjust_pivot_mode_starts_object_only_for_normal_gizmo_drags() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    mode_source = inspect.getsource(QtGhostRiggerMainWindow._set_pivot_edit_mode)

    assert 'self.settings_data["last_pivot_edit_mode"] = "affect_object_only"' in layout_source
    assert 'self.viewport.set_pivot_edit_mode("affect_object_only")' in layout_source
    assert "save_settings(self.settings_path, self.settings_data)" not in mode_source


def test_regular_properties_panel_can_omit_module_mesh_tab() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel(module_browser_enabled=False)
    tab_names = [panel.tabs.tabText(index) for index in range(panel.tabs.count())]

    assert tab_names == ["General"]
    assert panel.module_tab is None
    panel.select_module_meshes([])
    panel.refresh_module_mesh_rows()


def test_module_mesh_panel_omits_redundant_open_window_control() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import inspect

    from PySide6 import QtWidgets

    from src.gui.qt_lib.panels.qt_properties_panel import QtPropertiesPanel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    panel = QtPropertiesPanel()

    assert not hasattr(panel, "open_module_meshes_window_button")
    panel_source = inspect.getsource(QtPropertiesPanel._show_module_browser_context_menu)
    assert "Open Module Meshes Window" not in panel_source
    assert "moduleMeshesWindowRequested.emit" not in panel_source


def test_qt_overflow_helpers_scroll_dense_toolbar_rows() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore, QtWidgets

    from src.gui.qt_lib.assets.qt_theme import make_horizontal_overflow_area, make_scrollable_panel

    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    strip = QtWidgets.QWidget()
    strip.setMinimumWidth(900)
    strip_scroll = make_horizontal_overflow_area(strip, "TestToolbarScroll", height=40)
    strip_scroll.resize(240, 40)

    assert strip_scroll.widget() is strip
    assert strip_scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
    assert strip_scroll.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAlwaysOff
    assert strip.minimumWidth() >= 900

    panel = QtWidgets.QWidget()
    panel_scroll = make_scrollable_panel(panel, "TestDockScroll")

    assert panel_scroll.widget() is panel
    assert panel_scroll.widgetResizable() is True
    assert panel_scroll.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded
    assert panel_scroll.verticalScrollBarPolicy() == QtCore.Qt.ScrollBarAsNeeded


def test_main_window_command_bar_is_fixed_and_docks_are_scrollable() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    button_source = inspect.getsource(QtGhostRiggerMainWindow._tool_button)
    visibility_source = inspect.getsource(QtGhostRiggerMainWindow._on_detachable_panel_visibility)
    dock_source = inspect.getsource(QtGhostRiggerMainWindow._create_detachable_panel)

    assert "CommandBarScroll" not in command_source
    assert "host_layout.addWidget(bar, 1)" in command_source
    assert "visual_profile_combo" in command_source
    assert "make_scrollable_panel(widget" in dock_source
    assert 'f"{key}DockScroll"' in dock_source


def test_viewport_and_character_builder_toolbars_are_scrollable() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    viewport_source = inspect.getsource(QtViewportWidget._build)
    builder_source = inspect.getsource(QtCharacterBuilderWindow._build_toolbars)
    bottom_source = inspect.getsource(QtCharacterBuilderWindow._build_bottom_strip)

    assert "make_horizontal_overflow_area(" in viewport_source
    assert '"ViewportToolbarScroll"' in viewport_source
    assert "make_horizontal_overflow_area(" in builder_source
    assert '"CharacterBuilderToolbarScroll"' in builder_source
    assert "make_scrollable_panel(self.bottom_strip" in bottom_source


def test_main_window_moves_utility_tabs_to_tools_windows() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_diagnostics_panel import QtDiagnosticsPanel, QtDiagnosticsWindow
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
    assert "self.diagnostics_panel = QtDiagnosticsPanel(self._get_model, self)" in source
    assert "self.diagnostics_dock = self._create_detachable_panel(" in source
    assert "self.blueprint_window = QtBlueprintEditorWindow(self)" in source
    assert "self.texture_panel = self.texture_tool_window.texture_panel" in source
    assert "self.normal_map_panel = self.texture_tool_window.normal_map_panel" in source
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
    assert "Legacy Tk" not in actions_source
    assert "Legacy Tk" not in menu_source
    assert "_launch_legacy_tk" not in inspect.getsource(QtGhostRiggerMainWindow)

    model_menu_block = menu_source.split("mdlops_menu = self.menuBar().addMenu", 1)[0]
    assert "self.diag_action" not in model_menu_block

    for method_name in ("_open_texture_tool_window", "_open_blueprint_editor_window"):
        open_source = inspect.getsource(getattr(QtGhostRiggerMainWindow, method_name))
        assert "window.show()" in open_source
        assert "window.raise_()" in open_source

    diagnostics_source = inspect.getsource(QtGhostRiggerMainWindow._show_diagnostics_panel)
    assert "panel.run_diagnostics(self._current_model)" in diagnostics_source
    assert 'self._show_workspace_dock("diagnostics")' in diagnostics_source

    assert QtDiagnosticsPanel.__name__ == "QtDiagnosticsPanel"
    assert QtDiagnosticsWindow.__name__ == "QtDiagnosticsWindow"
    assert QtTextureToolWindow.__name__ == "QtTextureToolWindow"
    assert QtBlueprintEditorWindow.__name__ == "QtBlueprintEditorWindow"


def test_main_window_routes_library_and_animation_library_to_content_browser() -> None:
    import inspect

    from src.gui.qt_lib.panels.qt_content_browser_panel import QtContentBrowserPanel
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "self.content_browser_panel = QtContentBrowserPanel(self)" in source
    assert "self.library_panel = self.content_browser_panel" in source
    assert 'self.content_browser_dock = self._create_detachable_panel(' in source
    assert '"Content Browser"' in source
    assert '"content_browser",\n            "Content Browser",\n            self.content_browser_panel,\n            QtCore.Qt.LeftDockWidgetArea,' in source
    assert 'self.scene_dock = self._create_detachable_panel(' in source
    assert 'self.properties_dock = self._create_detachable_panel(' in source
    assert 'self.animations_dock = self._create_detachable_panel(' in source
    assert "self._stack_content_browser_under_scene()" in source
    stack_source = inspect.getsource(QtGhostRiggerMainWindow._stack_content_browser_under_scene)
    assert "self.splitDockWidget(self.scene_dock, self.content_browser_dock, QtCore.Qt.Vertical)" in stack_source
    assert "vertical_splitter.addWidget(self.viewport)" in source
    assert "left_tabs.addTab(" not in source
    assert "right_tabs.addTab(" not in source
    assert "self.animation_library_panel = self.content_browser_panel" in source
    assert "self.animation_library_combined_panel = QtAnimationLibraryCombinedPanel(" not in source
    assert "right_tabs.addTab(self.animation_library_panel" not in source
    assert "right_tabs.addTab(self.character_builder_panel" not in source
    assert "self.character_builder_panel = QtCharacterBuilderPanel" not in source

    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    assert '"Animation Library"' in actions_source
    assert 'self._show_content_browser("Animation")' in actions_source
    assert "self.content_browser_action" in actions_source
    assert "self.scene_panel_action" in actions_source
    assert "self.properties_panel_action" in actions_source

    module_source = inspect.getsource(QtGhostRiggerMainWindow._handle_module_action)
    assert 'self._open_blueprint_editor_window()' in module_source
    assert 'self._show_right_tab("Blueprint")' not in module_source

    assert QtContentBrowserPanel.__name__ == "QtContentBrowserPanel"


def test_main_command_strip_groups_dock_modules_on_right_and_sizes_like_viewport() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    command_source = inspect.getsource(QtGhostRiggerMainWindow._make_command_bar)
    actions_source = inspect.getsource(QtGhostRiggerMainWindow._build_actions)
    button_source = inspect.getsource(QtGhostRiggerMainWindow._tool_button)
    menu_source = inspect.getsource(QtGhostRiggerMainWindow._menu_button)
    visibility_source = inspect.getsource(QtGhostRiggerMainWindow._on_detachable_panel_visibility)

    assert 'layout.addWidget(self._tool_button("Scene Information", self.scene_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Properties", self.properties_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Sequence Editor", self.sequence_editor_action' in command_source
    assert 'layout.addWidget(self._tool_button("Nodes", self.nodes_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Lighting", self.lighting_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Cameras", self.camera_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Module Meshes", self.module_meshes_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Adjust Pivot", self.adjust_pivot_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("2DA Browser", self.twoda_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Resource Browser", self.resources_panel_action' in command_source
    assert 'layout.addWidget(self._tool_button("Diagnostics  Ctrl+D", self.diag_action' in command_source
    assert actions_source.count("self._configure_dock_toggle_action(") >= 12
    for action_name in (
        "content_browser_action",
        "scene_panel_action",
        "properties_panel_action",
        "sequence_editor_action",
        "nodes_panel_action",
        "lighting_panel_action",
        "camera_panel_action",
        "module_meshes_panel_action",
        "adjust_pivot_panel_action",
        "twoda_panel_action",
        "resources_panel_action",
        "diag_action",
    ):
        assert f"self.{action_name}" in actions_source
    assert "button.setCheckable(True)" in button_source
    assert "action.toggled.connect(button.setChecked)" in button_source
    assert "self._sync_dock_toggle_action(key, visible)" in visibility_source
    workspace_source = inspect.getsource(QtGhostRiggerMainWindow._show_workspace_dock)
    tab_source = inspect.getsource(QtGhostRiggerMainWindow._tab_workspace_dock_with_visible_peer)
    assert "self._tab_workspace_dock_with_visible_peer(key, dock)" in workspace_source
    assert "self.tabifyDockWidget(anchor, dock)" in tab_source
    assert '"Anims  Ctrl+A"' not in command_source
    assert command_source.index("layout.addStretch(1)") < command_source.index('"Scene Information"')
    assert "button.setFixedSize(30, 22)" in button_source
    assert "button.setIconSize(QtCore.QSize(18, 18))" in button_source
    assert "button.setFixedSize(34, 22)" in menu_source


def test_viewport_toolbar_flow_layout_centers_rows() -> None:
    import inspect

    from src.gui.qt_lib.assets.qt_theme import QtFlowLayout
    from src.gui.qt_lib.viewports.qt_viewport import QtViewportWidget

    flow_source = inspect.getsource(QtFlowLayout)
    viewport_source = inspect.getsource(QtViewportWidget._build)

    assert "horizontal_alignment" in flow_source
    assert "QtCore.Qt.AlignHCenter" in viewport_source
    assert "(max_width - current_width) // 2" in flow_source


def test_sequence_and_diagnostics_use_detachable_dock_registry() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    layout_source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    sequence_source = inspect.getsource(QtGhostRiggerMainWindow._show_sequence_editor_dock)
    diagnostics_source = inspect.getsource(QtGhostRiggerMainWindow._show_diagnostics_panel)
    default_area_source = inspect.getsource(QtGhostRiggerMainWindow._default_dock_area_for_key)

    assert '"sequence_editor": (1180, 720)' in layout_source
    assert '"diagnostics": (760, 560)' in layout_source
    assert "self.sequence_editor_dock = self._create_detachable_panel(" in layout_source
    assert '"sequence_editor",' in layout_source
    assert "self.diagnostics_dock = self._create_detachable_panel(" in layout_source
    assert '"diagnostics",' in layout_source
    assert 'self._show_workspace_dock("sequence_editor")' in sequence_source
    assert 'self._show_workspace_dock("diagnostics")' in diagnostics_source
    assert 'key in {"output_log", "sequence_editor"}' in default_area_source


def test_main_window_bottom_area_is_resizable_splitter() -> None:
    import inspect

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._build_layout)
    assert "vertical_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)" in source
    assert "self.vertical_splitter = vertical_splitter" in source
    assert "vertical_splitter.addWidget(self.viewport)" in source
    assert "vertical_splitter.addWidget(self.log_panel)" in source
    assert "root.addWidget(vertical_splitter, 1)" in source
    assert "main_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)" not in source
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
    from src.core.qt_core.geometry.model_data import Animation, KotorModel, ModelNode
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
    from src.core.qt_core.mdl.mdl_porter import MDLBinaryWriter
    from src.core.qt_core.geometry.model_data import ModelNode, NodeFlags

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
    from src.core.qt_core.mdl.mdl_porter import MDLBinaryWriter
    from src.core.qt_core.geometry.model_data import Animation, ModelNode

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
    from src.core.qt_core.mdl.mdl_writer import MDLBinaryWriter

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
    from src.core.qt_core.mdl.mdl_writer import MDLBinaryWriter
    from src.core.qt_core.geometry.model_data import Animation, ModelNode

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

    assert "from src.core.qt_core.mdl.mdl_writer import MDLBinaryWriter" in source


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


def test_scene_animation_entries_collect_all_runtime_models() -> None:
    from types import SimpleNamespace

    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    window = SimpleNamespace()
    anim_walk = SimpleNamespace(name="walk", length=1.0)
    anim_talk = SimpleNamespace(name="talk", length=2.0)
    bith = SimpleNamespace(name="N_Bith", animations=[anim_walk])
    malak = SimpleNamespace(name="N_DarthMalak", animations=[anim_talk])
    window.scene_manager = SimpleNamespace(
        active_scene=SimpleNamespace(
            objects=[
                SimpleNamespace(
                    id="obj-bith",
                    name="Cantina Bith",
                    source_ref=SimpleNamespace(game="K1", resref="n_bith"),
                    metadata={"_runtime_model": bith},
                ),
                SimpleNamespace(
                    id="obj-malak",
                    name="Malak",
                    source_ref=SimpleNamespace(game="K1", resref="n_darthmalak"),
                    metadata={"_runtime_model": malak},
                ),
            ]
        )
    )
    window._infer_game_from_model = lambda _model: "K1"

    entries = QtGhostRiggerMainWindow._collect_scene_animation_entries(window)

    assert {entry["animation"] for entry in entries} == {"walk", "talk"}
    assert {entry["object_name"] for entry in entries} == {"Cantina Bith", "Malak"}
    assert {entry["resref"] for entry in entries} == {"n_bith", "n_darthmalak"}


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

    from src.core.qt_core.geometry.model_data import ModelNode
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


def test_quinn_aliases_include_real_kotor_mesh_bone_nodes() -> None:
    import pytest

    from src.core.geometry.model_data import ModelNode, NodeFlags
    from src.unreal.animation_retargeting import build_bone_map
    from src.unreal.quinn import QUINN_BONE_MAP, load_quinn_skeleton_asset, unreal_skeleton_model

    if not QUINN_BONE_MAP.exists():
        pytest.skip("SKM_Quinn_Simple_BoneMap.xml not available")

    source = SimpleNamespace(
        name="S_Male02",
        all_nodes=lambda: [
            ModelNode(name="pelvis_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="torso_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="torsoUpr_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="neck_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rCollar_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rbicep_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rbicepL_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rforearm_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rhand_g", flags=int(NodeFlags.MESH)),
            ModelNode(name="rhand"),
            ModelNode(name="Torso", flags=int(NodeFlags.SKIN)),
        ],
    )
    target = unreal_skeleton_model(load_quinn_skeleton_asset())

    report = build_bone_map(source, target)

    assert report.mapping["pelvis_g"] == "pelvis"
    assert report.mapping["torso_g"] == "spine_02"
    assert report.mapping["torsoupr_g"] in {"spine_03", "spine_04", "spine_01"}
    assert report.mapping["neck_g"] == "neck_01"
    assert report.mapping["rcollar_g"] == "clavicle_r"
    assert report.mapping["rbicep_g"] == "upperarm_r"
    assert report.mapping["rbicepl_g"] == "lowerarm_r"
    assert report.mapping["rforearm_g"] == "lowerarm_r"
    assert report.mapping["rhand_g"] == "hand_r"
    assert report.mapping["rhand"] == "hand_r"
    assert "torso" not in report.mapping


def test_unreal_bone_map_excludes_dummy_and_hook_helpers() -> None:
    from src.core.qt_core.geometry.model_data import ModelNode
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

    from src.core.qt_core.geometry.model_data import Animation, KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import Animation, KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import Animation, KotorModel, ModelNode
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

        assert window.source_viewport._use_gpu is True
        assert window.target_viewport._use_gpu is True
    finally:
        window.close()


def test_retarget_pose_applies_source_bind_relative_rotation_to_target_bind() -> None:
    import math

    import pytest

    from src.core.qt_core.animation.animation_engine import AnimPose, NodePose
    from src.core.qt_core.animation_retargeting.retargeter import retarget_pose
    from src.core.qt_core.geometry.model_data import ModelNode

    src_bind = (0.0, 0.0, math.sin(math.radians(45.0)), math.cos(math.radians(45.0)))
    target_bind = (0.0, math.sin(math.radians(15.0)), 0.0, math.cos(math.radians(15.0)))
    source = SimpleNamespace(name="source", all_nodes=lambda: [ModelNode(name="RHand", rotation=src_bind)])
    target = SimpleNamespace(name="target", all_nodes=lambda: [ModelNode(name="RHand", rotation=target_bind)])
    pose = AnimPose(nodes={"rhand": NodePose(name="RHand", rotation=src_bind)})

    result = retarget_pose(pose, source, target)

    assert result.pose.nodes["rhand"].rotation == pytest.approx(target_bind)


def test_manual_bone_map_override_drives_retarget_pose() -> None:
    from src.core.qt_core.animation.animation_engine import AnimPose, NodePose
    from src.core.qt_core.animation_retargeting.retargeter import build_bone_map, retarget_pose
    from src.core.qt_core.geometry.model_data import ModelNode

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

    from src.core.qt_core.animation.animation_engine import AnimPose, NodePose
    from src.core.qt_core.animation_retargeting.retargeter import RetargetConfig, retarget_pose
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode

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
    from src.core.qt_core.geometry.model_data import ModelNode
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

    from src.core.qt_core.animation.animation_engine import AnimPose, NodePose
    from src.core.qt_core.geometry.model_data import KotorModel, ModelNode
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

    from src.core.qt_core.geometry.model_data import Animation, KotorModel, ModelNode
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

    from src.gui.qt_lib.rendering import gpu_renderer

    source = inspect.getsource(gpu_renderer._build_vbo_data)
    assert "apply_skin_node_transform_for_bind" in source
    assert "not is_skin or bool(apply_skin_node_transform_for_bind)" in source
    assert "elif _node_vs == 1 or is_skin" in source
