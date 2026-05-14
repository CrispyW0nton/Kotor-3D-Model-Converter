from __future__ import annotations

from types import SimpleNamespace


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


def test_gpu_vbo_applies_node_local_transform_to_skin_nodes() -> None:
    import inspect

    from src.gui import gpu_renderer

    source = inspect.getsource(gpu_renderer._build_vbo_data)
    assert "if _node_vs == 0:  # NODE_LOCAL" in source
    assert "if _node_vs == 0 and is_skin" not in source
