from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest


K1_PATH = Path(os.environ.get("K1_PATH", r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"))
K2_PATH = Path(os.environ.get("K2_PATH", r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"))


def _resource_manager():
    from src.core.qt_core.assets.resource_manager import ResourceManager

    manager = ResourceManager()
    if K1_PATH.exists():
        manager.set_k1_dir(str(K1_PATH))
    if K2_PATH.exists():
        manager.set_k2_dir(str(K2_PATH))
    return manager


def _raw_model(game: str, resref: str) -> tuple[bytes, bytes]:
    manager = _resource_manager()
    mdl = manager.get_mdl(resref, game.upper())
    if mdl is None:
        pytest.skip(f"{game}:{resref} not available in local test install")
    return mdl, manager.get_mdx(resref, game.upper()) or b""


def _reader_for(game: str, resref: str):
    from src.core.qt_core.mdl.ghostrigger_mdl_reader import GhostRiggerMDLBinaryReader

    mdl, mdx = _raw_model(game, resref)
    reader = GhostRiggerMDLBinaryReader(mdl, source_ext=mdx)
    model = reader.load()
    return reader, model


def _nodes_by_name(model) -> dict[str, object]:
    return {node.name.lower(): node for node in model.all_nodes()}


def test_bug_c_composite_offset_applies_to_skin_nodes() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="head_skin",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=True,
        vertex_space=0,
        skin_data=[],
        _composite_nonskin_offset=(10.0, 20.0, 30.0),
    )

    vbo, indices = _build_vbo_data(node, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))

    assert indices is None
    assert vbo is not None
    assert vbo[:, 0:3].tolist() == [
        [10.0, 20.0, 30.0],
        [11.0, 20.0, 30.0],
        [10.0, 21.0, 30.0],
    ]


def test_skin_bind_pose_vbo_applies_node_local_transform() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="body_skin",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=True,
        vertex_space=0,
        skin_data=[],
    )

    vbo, indices = _build_vbo_data(node, (10.0, 20.0, 30.0), (0.0, 0.0, 0.0, 1.0))

    assert indices is None
    assert vbo is not None
    assert vbo[:, 0:3].tolist() == [
        [11.0, 22.0, 33.0],
        [12.0, 22.0, 33.0],
        [11.0, 23.0, 33.0],
    ]


def test_animated_skin_vbo_can_keep_authored_input_coordinates() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="body_skin",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=True,
        vertex_space=0,
        skin_data=[],
    )

    vbo, indices = _build_vbo_data(
        node,
        (10.0, 20.0, 30.0),
        (0.0, 0.0, 0.0, 1.0),
        apply_skin_node_transform_for_bind=False,
    )

    assert indices is None
    assert vbo is not None
    assert vbo[:, 0:3].tolist() == [
        [1.0, 2.0, 3.0],
        [2.0, 2.0, 3.0],
        [1.0, 3.0, 3.0],
    ]


def test_gpu_vbo_handles_module_mesh_without_uvs() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="area_piece",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=False,
        vertex_space=0,
    )

    vbo, indices = _build_vbo_data(node, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0), is_module=True)

    assert vbo is not None
    assert indices is not None
    assert indices.tolist() == [0, 1, 2]
    assert vbo[:, 6:8].tolist() == [[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]]


def test_k1_m02aa_01a_module_model_loads_and_renders_without_crashing() -> None:
    from src.core.qt_core.game.kotor_loader import load_model_from_bytes
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    mdl, mdx = _raw_model("k1", "m02aa_01a")
    model = load_model_from_bytes(mdl, mdx)

    assert model is not None
    assert model.node_count() == 127
    assert len(model.mesh_nodes()) == 56
    assert getattr(model, "classification", None) == "effect"

    renderer = FrameRenderer(ArcBallCamera())
    renderer.set_model(model)
    renderer.show_texture = True
    image = renderer.render(320, 240)

    assert image is not None
    assert image.size == (320, 240)


def test_ad_saul_binary_skin_bind_matches_ascii_fixture() -> None:
    import numpy as np

    from src.core.qt_core.game.kotor_loader import load_model_from_file
    from src.core.qt_core.mdl.mdl_parser import MDLAsciiParser
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    fixture_root = Path(__file__).parent / "modeltests" / "kotor_tool_1.0.3.4"
    ascii_path = fixture_root / "mdlops_ascii" / "ad_saul" / "ad_saul-ascii.mdl"
    binary_path = fixture_root / "mdlops_binary" / "ad_saul" / "ad_saul.mdl"
    mdx_path = fixture_root / "mdlops_binary" / "ad_saul" / "ad_saul.mdx"
    if not ascii_path.exists() or not binary_path.exists() or not mdx_path.exists():
        pytest.skip("ad_saul ASCII/binary fixtures are not available")

    ascii_model = MDLAsciiParser().parse_file(str(ascii_path))
    binary_model = load_model_from_file(binary_path, mdx_path)

    ascii_nodes = _nodes_by_name(ascii_model)
    binary_nodes = _nodes_by_name(binary_model)

    for node_name in ("head", "tongue"):
        ascii_node = ascii_nodes[node_name]
        binary_node = binary_nodes[node_name]
        assert not getattr(ascii_node, "is_skin", False)
        assert getattr(binary_node, "is_skin", False)

        a_pos, a_orient = ascii_node.world_transform()
        b_pos, b_orient = binary_node.world_transform()
        ascii_vbo, _ = _build_vbo_data(ascii_node, a_pos, a_orient)
        binary_vbo, _ = _build_vbo_data(binary_node, b_pos, b_orient)

        assert ascii_vbo is not None
        assert binary_vbo is not None
        ascii_bounds = np.vstack([ascii_vbo[:, 0:3].min(axis=0), ascii_vbo[:, 0:3].max(axis=0)])
        binary_bounds = np.vstack([binary_vbo[:, 0:3].min(axis=0), binary_vbo[:, 0:3].max(axis=0)])
        np.testing.assert_allclose(binary_bounds, ascii_bounds, atol=1e-5, rtol=0.0)


def test_gpu_skin_bone_id_attribute_contract_is_integer() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import (
        _VBO_BONE_IDS_FORMAT,
        _VBO_MAIN_FORMAT,
        _VERT_SRC,
    )

    assert "in ivec4 in_bone_ids" in _VERT_SRC
    assert "in vec4  in_bone_ids" not in _VERT_SRC
    assert "int  bi = in_bone_ids[i]" in _VERT_SRC
    assert _VBO_BONE_IDS_FORMAT == "4i"
    assert _VBO_MAIN_FORMAT == "3f 3f 2f 2f 4f 4f"


def test_gpu_skin_bone_ids_split_to_int32_buffer() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data, _split_vbo_attributes_for_gpu

    node = SimpleNamespace(
        name="body_skin",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=True,
        vertex_space=0,
        skin_data=[
            SimpleNamespace(influences=[
                SimpleNamespace(bone_index=0, weight=0.25),
                SimpleNamespace(bone_index=1, weight=0.75),
            ])
        ] * 3,
    )

    vbo, _indices = _build_vbo_data(
        node,
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
        bone_index_remap={0: 7, 1: 19},
    )
    main_vbo, bone_ids = _split_vbo_attributes_for_gpu(vbo)

    assert main_vbo.dtype.name == "float32"
    assert bone_ids.dtype.name == "int32"
    assert bone_ids[0].tolist() == [7, 19, 0, 0]
    assert main_vbo[0, 14:18].tolist() == [0.25, 0.75, 0.0, 0.0]


def test_vbo_expanded_path_uses_per_face_lightmap_uvs() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="lightmapped_seam_quad",
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (0.75, 0.25)],
        uvs_lm=[(0.1, 0.1), (0.2, 0.2), (0.3, 0.3), (0.9, 0.8)],
        faces=[(0, 1, 2)],
        face_uvs=[(0, 3, 2)],
        is_skin=False,
        vertex_space=1,
        skin_data=[],
    )

    vbo, indices = _build_vbo_data(node, (0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0))

    assert indices is None
    assert vbo is not None
    assert vbo[1, 6:8].tolist() == pytest.approx([0.75, 0.25])
    assert vbo[1, 8:10].tolist() == pytest.approx([0.9, 0.8])


def test_qbone_inverse_bind_matrix_uses_skin_slot_data() -> None:
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    inv_bind = MatrixPaletteUploader.qbone_inverse_bind_matrix(
        (0.0, 0.0, 0.0, 1.0),
        (1.0, 2.0, 3.0),
    )

    assert inv_bind == [
        [1.0, 0.0, 0.0, -1.0],
        [0.0, 1.0, 0.0, -2.0],
        [0.0, 0.0, 1.0, -3.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def test_qbone_direct_bind_matrix_uses_authored_tr_order() -> None:
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    direct_bind = MatrixPaletteUploader.qbone_direct_bind_matrix(
        (0.0, 0.0, 0.0, 1.0),
        (1.0, 2.0, 3.0),
    )

    assert direct_bind == [
        [1.0, 0.0, 0.0, 1.0],
        [0.0, 1.0, 0.0, 2.0],
        [0.0, 0.0, 1.0, 3.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def test_skin_node_palette_restores_3f_qbone_tbone_path(monkeypatch) -> None:
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=None,
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=[(0.0, 0.0, 0.0, 1.0)],
        tbone_list=[(1.0, 0.0, 0.0)],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(3.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })
    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F1_current_TR_inverse")
    uploader = MatrixPaletteUploader(max_bones=4)

    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, pose)
    palette = uploader.as_numpy_array()

    assert uploader.palette[0].bone_name == "Arm"
    assert uploader._skin_local_inv_bind_by_slot[0][0][3] == pytest.approx(-1.0)
    assert uploader._skin_local_direct_bind_by_slot[0][0][3] == pytest.approx(1.0)
    assert uploader._skin_palette_formula == "F1_current_TR_inverse"
    assert uploader._skin_inverse_bind_source == "qBone_tBone_inverse_TR"
    assert uploader._skin_bind_matrix[0][3] == pytest.approx(10.0)
    assert palette[0, 0, 3] == pytest.approx(2.0)


def test_skin_node_palette_without_qbones_uses_hierarchy_bind(monkeypatch) -> None:
    """Imported FBX skins have weights but no KotOR qBone/tBone arrays."""
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=root,
        position=(1.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=[],
        tbone_list=[],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(3.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })
    monkeypatch.delenv("GHOSTRIGGER_SKIN_FORMULA", raising=False)
    uploader = MatrixPaletteUploader(max_bones=4)

    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, pose)
    palette = uploader.as_numpy_array()

    assert uploader._skin_inverse_bind_source == "hierarchy_inverse_bind_no_qbone"
    assert palette[0, 0, 3] == pytest.approx(2.0)


def test_skin_node_palette_env_switch_F11_rotation_only_wrapper(
    monkeypatch,
) -> None:
    """3i Step 7 — env-gated F11 wrapper formula switch.

    F1 remains available as an explicit legacy comparison palette. Setting
    ``GHOSTRIGGER_SKIN_FORMULA=F11_rotation_only_skin_bind_wrapper`` swaps
    the per-bone matrix to ``inv(R(skin_bind)) * world_pose * inv_bind *
    R(skin_bind)``.  For an identity skin-bind rotation (this fixture)
    F11 must collapse to F1 — the ``c_drexlf``/``c_brith`` no-op control.
    """
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=None,
        position=(10.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=[(0.0, 0.0, 0.0, 1.0)],
        tbone_list=[(1.0, 0.0, 0.0)],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(3.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F11_rotation_only_skin_bind_wrapper")
    uploader_f11 = MatrixPaletteUploader(max_bones=4)
    uploader_f11.build_inverse_bind_pose(model)
    uploader_f11.compute_skin_node_palette(skin_node, pose)
    palette_f11 = uploader_f11.as_numpy_array()
    assert uploader_f11._skin_palette_formula == "F11_rotation_only_skin_bind_wrapper"

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F1_current_TR_inverse")
    uploader_f1 = MatrixPaletteUploader(max_bones=4)
    uploader_f1.build_inverse_bind_pose(model)
    uploader_f1.compute_skin_node_palette(skin_node, pose)
    palette_f1 = uploader_f1.as_numpy_array()
    assert uploader_f1._skin_palette_formula == "F1_current_TR_inverse"

    assert palette_f1.shape == palette_f11.shape
    assert palette_f1[0, 0, 3] == pytest.approx(2.0)
    diff = float((palette_f11 - palette_f1).max() - (palette_f11 - palette_f1).min())
    assert diff == pytest.approx(0.0, abs=1e-9)


def test_skin_node_palette_env_switch_F11_diverges_with_nonidentity_skin_bind(
    monkeypatch,
) -> None:
    """3i Step 7 — F11 must materially differ from F1 when the skin-node
    bind has a non-identity rotation component.

    This mirrors the ``c_bomabeast`` falsification target: nodes whose
    ``skin_bind`` rotation is non-identity (e.g. lowerbody/pelvis) will
    see a rotation-only outer wrapper change the palette, which is the
    precondition for the headless visual gate to produce new evidence.
    """
    import math
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    half = math.sin(math.radians(45.0))
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, half, math.cos(math.radians(45.0))),
        bone_map=["Arm"],
        qbone_list=[(0.0, 0.0, 0.0, 1.0)],
        tbone_list=[(1.0, 0.0, 0.0)],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(3.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F11_rotation_only_skin_bind_wrapper")
    uploader_f11 = MatrixPaletteUploader(max_bones=4)
    uploader_f11.build_inverse_bind_pose(model)
    uploader_f11.compute_skin_node_palette(skin_node, pose)
    palette_f11 = uploader_f11.as_numpy_array()

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F1_current_TR_inverse")
    uploader_f1 = MatrixPaletteUploader(max_bones=4)
    uploader_f1.build_inverse_bind_pose(model)
    uploader_f1.compute_skin_node_palette(skin_node, pose)
    palette_f1 = uploader_f1.as_numpy_array()

    delta = float(abs(palette_f11 - palette_f1).max())
    assert delta > 0.5, (
        "F11 wrapper must diverge from F1 when skin_bind has non-identity "
        "rotation; otherwise the c_bomabeast gate cannot produce evidence."
    )


def test_skin_node_palette_env_switch_unknown_value_falls_back_to_G5(
    monkeypatch,
) -> None:
    """Unknown env values must silently fall back to production G5."""
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Root"],
        qbone_list=[(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)],
        tbone_list=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, skin_node])

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "definitely_not_a_real_formula")
    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, anim_pose=None)
    assert uploader._skin_palette_formula == "G5_FULL_REF"


def test_skin_node_palette_auto_profile_uses_dfs_qbone_for_full_arrays(
    monkeypatch,
) -> None:
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    monkeypatch.delenv("GHOSTRIGGER_SKIN_FORMULA", raising=False)
    root = SimpleNamespace(name="Root", parent=None, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    extra = SimpleNamespace(name="Extra", parent=root, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    arm = SimpleNamespace(name="Arm", parent=extra, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    qbones = [(1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0)]
    tbones = [(0, 0, 0), (0, 0, 0), (5, 0, 0), (0, 0, 0)]
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0, 0, 0),
        rotation=(0, 0, 0, 1),
        bone_map=["Arm"],
        qbone_list=qbones,
        tbone_list=tbones,
    )
    model = SimpleNamespace(name="dfs_model", all_nodes=lambda: [root, extra, arm, skin_node])
    pose = SimpleNamespace(nodes={"arm": SimpleNamespace(position=(0, 0, 0), rotation=(0, 0, 0, 1))})

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, pose)
    palette = uploader.as_numpy_array()

    assert uploader._skin_palette_formula == "G5_FULL_REF"
    assert uploader._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"
    assert "auto:dfs_qbone" in uploader._skin_profile_reason
    assert palette[0, 0, 3] == pytest.approx(5.0, abs=1e-6)


def test_skin_node_palette_auto_profile_uses_compact_qbone_for_local_arrays(
    monkeypatch,
) -> None:
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    monkeypatch.delenv("GHOSTRIGGER_SKIN_FORMULA", raising=False)
    root = SimpleNamespace(name="Root", parent=None, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    arm = SimpleNamespace(name="Arm", parent=root, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0, 0, 0),
        rotation=(0, 0, 0, 1),
        bone_map=["Arm"],
        qbone_list=[(0, 0, 0, 1)],
        tbone_list=[(1, 0, 0)],
    )
    model = SimpleNamespace(name="compact_model", all_nodes=lambda: [root, arm, skin_node])
    pose = SimpleNamespace(nodes={"arm": SimpleNamespace(position=(3, 0, 0), rotation=(0, 0, 0, 1))})

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, pose)
    palette = uploader.as_numpy_array()

    assert uploader._skin_palette_formula == "F1_current_TR_inverse"
    assert uploader._skin_inverse_bind_source == "qBone_tBone_inverse_TR"
    assert "auto:compact_qbone" in uploader._skin_profile_reason
    assert palette[0, 0, 3] == pytest.approx(2.0, abs=1e-6)


def test_skinning_species_classifier_covers_primary_character_families() -> None:
    from src.core.qt_core.animation.gpu_skinning import (
        SKINNING_SPECIES_PROFILES,
        classify_skinning_species,
    )

    expected = {
        "human": ("ad_saul", "N_AdmrlSaulKar"),
        "bith": ("n_bith", "S_Male02"),
        "droid": ("p_hk47", "NULL"),
        "utility_droid": ("p_t3m4", "NULL"),
        "battle_droid": ("c_drdwar", "NULL"),
        "yoda": ("n_yoda", "S_Male02"),
        "mandalorian": ("n_mandalorian", "S_Female02"),
        "gamorrean": ("c_gammorean", "NULL"),
    }

    for species, (model_name, supermodel) in expected.items():
        assert classify_skinning_species(model_name, supermodel) == species
        assert species in SKINNING_SPECIES_PROFILES


def test_skin_node_palette_records_species_profile_reason(monkeypatch) -> None:
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    monkeypatch.delenv("GHOSTRIGGER_SKIN_FORMULA", raising=False)
    root = SimpleNamespace(name="Root", parent=None, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    arm = SimpleNamespace(name="Arm", parent=root, position=(0, 0, 0), rotation=(0, 0, 0, 1))
    skin_node = SimpleNamespace(
        name="BithSkin",
        parent=root,
        position=(0, 0, 0),
        rotation=(0, 0, 0, 1),
        bone_map=["Arm"],
        qbone_list=[(1, 0, 0, 0), (1, 0, 0, 0), (1, 0, 0, 0)],
        tbone_list=[(0, 0, 0), (0, 0, 0), (0, 0, 0)],
    )
    model = SimpleNamespace(
        name="n_bith",
        supermodel="S_Male02",
        all_nodes=lambda: [root, arm, skin_node],
    )

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, SimpleNamespace(nodes={}))

    assert uploader._skin_species == "bith"
    assert uploader._skin_species_profile.label == "Bith"
    assert uploader._skin_palette_formula == "G5_FULL_REF"
    assert "species:bith" in uploader._skin_profile_reason
    assert "auto:dfs_qbone" in uploader._skin_profile_reason


# ─────────────────────────────────────────────────────────────────────────────
# 3j Step 4 — env-gated G5_FULL_REF (DFS-indexed, W-first, no invert) tests
# ─────────────────────────────────────────────────────────────────────────────


def test_skin_uploader_populates_name_to_dfs_index() -> None:
    """3j Step 4 — ``build_inverse_bind_pose`` must build a name -> DFS
    index lookup parallel to ``model.all_nodes()`` so the G5 path can
    address ``qbones[]``/``tbones[]`` by global node order rather than
    by the compact ``bone_map`` slot.
    """
    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    extra = SimpleNamespace(
        name="ExtraNode",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=extra,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=[],
        qbone_list=[],
        tbone_list=[],
    )
    model = SimpleNamespace(all_nodes=lambda: [root, extra, arm, skin_node])

    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)

    assert uploader._name_to_dfs_index == {
        "root": 0,
        "extranode": 1,
        "arm": 2,
        "skinmesh": 3,
    }


def test_skin_node_palette_env_switch_G5_uses_dfs_indexed_qbone(
    monkeypatch,
) -> None:
    """3j Step 4 — ``GHOSTRIGGER_SKIN_FORMULA=G5_FULL_REF`` must address
    ``qbones[]``/``tbones[]`` by the influenced bone's GLOBAL DFS NODE
    INDEX, not by the compact ``bone_map`` slot index that F1 (production)
    uses.

    Fixture lays out 4 nodes (Root, ExtraNode, Arm, SkinMesh) so that
    ``Arm`` is at DFS index 2 but slot 0 in the skin node's bone_map.
    The qbone/tbone arrays are length == node count and only the entry
    at DFS index 2 carries a non-identity translation. F1 reads slot 0
    and sees identity; G5 reads DFS index 2 and sees the translation.
    """
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    extra = SimpleNamespace(
        name="ExtraNode",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=extra,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    # qbone_list/tbone_list are parallel to global DFS order. Arm sits at
    # DFS index 2; only that slot carries a non-trivial translation. The
    # quaternion bytes are written W-first (qb[0]=1.0 is the W component)
    # so that the G5 helper produces an identity rotation.
    qbones = [
        (1.0, 0.0, 0.0, 0.0),  # DFS 0 (Root)
        (1.0, 0.0, 0.0, 0.0),  # DFS 1 (ExtraNode)
        (1.0, 0.0, 0.0, 0.0),  # DFS 2 (Arm)  <-- G5 reads this one
        (1.0, 0.0, 0.0, 0.0),  # DFS 3 (SkinMesh)
    ]
    tbones = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (5.0, 0.0, 0.0),       # DFS 2 (Arm)  <-- G5 reads this one
        (0.0, 0.0, 0.0),
    ]
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=qbones,
        tbone_list=tbones,
    )
    model = SimpleNamespace(all_nodes=lambda: [root, extra, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "G5_FULL_REF")
    g5 = MatrixPaletteUploader(max_bones=4)
    g5.build_inverse_bind_pose(model)
    g5.compute_skin_node_palette(skin_node, pose)
    palette_g5 = g5.as_numpy_array()
    assert g5._skin_palette_formula == "G5_FULL_REF"
    assert g5._skin_inverse_bind_source == "qBone_tBone_dfs_indexed_TR_no_invert"

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F1_current_TR_inverse")
    f1 = MatrixPaletteUploader(max_bones=4)
    f1.build_inverse_bind_pose(model)
    f1.compute_skin_node_palette(skin_node, pose)
    palette_f1 = f1.as_numpy_array()
    assert f1._skin_palette_formula == "F1_current_TR_inverse"
    assert f1._skin_inverse_bind_source == "qBone_tBone_inverse_TR"

    # F1 reads qbones[slot=0] / tbones[slot=0] — Root's identity payload
    # — then inverts identity, so the palette translation is zero.
    assert palette_f1[0, 0, 3] == pytest.approx(0.0, abs=1e-6)
    # G5 reads qbones[dfs=2] / tbones[dfs=2] — Arm's (5,0,0) translation
    # — and treats T*R as the inverse-bind directly, so the palette
    # carries +5 in the X column. This is exactly the indexing fix that
    # 3j-3 identified as the third compounding bug.
    assert palette_g5[0, 0, 3] == pytest.approx(5.0, abs=1e-6)
    assert float(abs(palette_g5 - palette_f1).max()) > 0.5


def test_skin_node_palette_env_switch_G5_decodes_quaternion_w_first(
    monkeypatch,
) -> None:
    """3j Step 4 — G5 must decode quaternion bytes as ``(w, x, y, z)``,
    matching reone/KotOR.js/PyKotor's node-header reader. F1 decodes the
    same bytes as ``(x, y, z, w)``, so for a quaternion whose disk
    layout puts a non-trivial W component first the two paths must
    produce different inverse-bind matrices.

    Fixture pins DFS index == slot index so the only remaining axis of
    variation is the byte order — isolating the convention bug from the
    indexing bug exercised in the previous test.
    """
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    # 90 deg rotation in W-first encoding: cos(45) at [0], sin(45) along Z at [3].
    # F1 will misread this as a 90 deg rotation about X (qx=cos(45),
    # qz=sin(45) is a non-unit interpretation that re-normalises into
    # something completely different from a Z-rotation).
    cos45 = 0.7071067811865475
    sin45 = 0.7071067811865475
    qbones = [
        (1.0, 0.0, 0.0, 0.0),  # DFS 0 (Root) — identity
        (cos45, 0.0, 0.0, sin45),  # DFS 1 (Arm) — 90 deg about Z under W-first
    ]
    tbones = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
    ]
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=qbones,
        tbone_list=tbones,
    )
    model = SimpleNamespace(all_nodes=lambda: [root, arm, skin_node])
    # Skip SkinMesh DFS slot for qbone/tbone arrays — under the G5
    # convention the skin node carries no influence and its own qbone is
    # never sampled. Pad to length so the lookup is safe.
    qbones.append((1.0, 0.0, 0.0, 0.0))
    tbones.append((0.0, 0.0, 0.0))
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "G5_FULL_REF")
    g5 = MatrixPaletteUploader(max_bones=4)
    g5.build_inverse_bind_pose(model)
    g5.compute_skin_node_palette(skin_node, pose)
    inv_bind_g5 = g5._skin_local_inv_bind_by_slot[0]

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "F1_current_TR_inverse")
    f1 = MatrixPaletteUploader(max_bones=4)
    f1.build_inverse_bind_pose(model)
    f1.compute_skin_node_palette(skin_node, pose)
    inv_bind_f1 = f1._skin_local_inv_bind_by_slot[0]

    # G5 W-first decoding of (cos45, 0, 0, sin45) = quat(w=cos45, z=sin45)
    # = a 90 deg rotation about +Z, which sends (1,0,0) -> (0, 1, 0).
    # The inverse-bind matrix in row-major form therefore has entries:
    #   row 0: (cos90, -sin90, 0, 0) = (0, -1, 0, 0)
    #   row 1: (sin90,  cos90, 0, 0) = (1,  0, 0, 0)
    assert inv_bind_g5[0][0] == pytest.approx(0.0, abs=1e-6)
    assert inv_bind_g5[0][1] == pytest.approx(-1.0, abs=1e-6)
    assert inv_bind_g5[1][0] == pytest.approx(1.0, abs=1e-6)
    assert inv_bind_g5[1][1] == pytest.approx(0.0, abs=1e-6)

    # F1 X-first decoding of the same bytes lands somewhere else
    # entirely (then inverts T*R), so the matrices must materially
    # differ. We assert max-abs delta rather than a specific value so a
    # later refactor of F1 doesn't break this test for an unrelated reason.
    delta_rows = [
        abs(inv_bind_g5[i][j] - inv_bind_f1[i][j])
        for i in range(4)
        for j in range(4)
    ]
    assert max(delta_rows) > 0.5


def test_skin_node_palette_env_switch_G5_cpu_to_uploaded_bytes_parity(
    monkeypatch,
) -> None:
    """3j Step 4 - CPU <-> uploaded palette parity under G5_FULL_REF.

    The renderer uploads the palette to the SSBO via
    ``MatrixPaletteUploader.as_flat_bytes()`` (column-major float32 per
    matrix, padded to ``max_bones`` with identities). The CPU LBS path
    consumes ``MatrixPaletteUploader.as_numpy_array()`` (row-major
    float32 NxN). For audit parity we must prove that under G5 the two
    representations describe the same matrices bit-exactly --- if they
    diverge, GhostRigger's CPU validation tests would silently disagree
    with what the GPU actually renders.

    The test builds a synthetic 4-node fixture exercising all three
    G5 fixes simultaneously (DFS index != slot, W-first quaternion,
    no inversion), takes both representations, round-trips the bytes
    back into a NumPy view, and asserts:

      - the CPU-side row-major palette equals the round-tripped
        column-major upload bytes element-for-element
      - both describe a bone matrix whose translation column carries
        the +5 X displacement that only the G5 path produces (so the
        test would also fail if compute_skin_node_palette silently
        regressed to F1 under the env switch).
    """
    import struct

    import numpy as np
    import pytest

    from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader

    root = SimpleNamespace(
        name="Root",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    extra = SimpleNamespace(
        name="ExtraNode",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    arm = SimpleNamespace(
        name="Arm",
        parent=extra,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    qbones = [
        (1.0, 0.0, 0.0, 0.0),  # DFS 0 (Root)
        (1.0, 0.0, 0.0, 0.0),  # DFS 1 (ExtraNode)
        (1.0, 0.0, 0.0, 0.0),  # DFS 2 (Arm)  <-- G5 reads this one
        (1.0, 0.0, 0.0, 0.0),  # DFS 3 (SkinMesh)
    ]
    tbones = [
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.0),
        (5.0, 0.0, 0.0),       # DFS 2 (Arm)  <-- G5 reads this one
        (0.0, 0.0, 0.0),
    ]
    skin_node = SimpleNamespace(
        name="SkinMesh",
        parent=root,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        bone_map=["Arm"],
        qbone_list=qbones,
        tbone_list=tbones,
    )
    model = SimpleNamespace(all_nodes=lambda: [root, extra, arm, skin_node])
    pose = SimpleNamespace(nodes={
        "arm": SimpleNamespace(
            position=(0.0, 0.0, 0.0),
            rotation=(0.0, 0.0, 0.0, 1.0),
        )
    })

    monkeypatch.setenv("GHOSTRIGGER_SKIN_FORMULA", "G5_FULL_REF")
    uploader = MatrixPaletteUploader(max_bones=4)
    uploader.build_inverse_bind_pose(model)
    uploader.compute_skin_node_palette(skin_node, pose)
    palette_cpu = uploader.as_numpy_array()
    upload_bytes = uploader.as_flat_bytes()

    assert palette_cpu is not None
    assert palette_cpu.shape == (1, 4, 4)
    assert palette_cpu.dtype == np.float32

    # The upload payload is padded to ``max_bones`` with identities. We
    # restrict the comparison to the ``len(palette)`` real entries.
    flat_count = uploader._max_bones * 16
    floats = struct.unpack(f"{flat_count}f", upload_bytes)
    upload_arr = np.zeros((uploader._max_bones, 4, 4), dtype=np.float32)
    for slot in range(uploader._max_bones):
        for r in range(4):
            for c in range(4):
                upload_arr[slot, r, c] = floats[slot * 16 + c * 4 + r]

    bone_count = len(uploader.palette)
    diff = np.max(
        np.abs(palette_cpu[:bone_count] - upload_arr[:bone_count])
    )
    assert float(diff) == 0.0, (
        "CPU palette (as_numpy_array) and uploaded palette (as_flat_bytes) "
        "must agree bit-exactly under G5_FULL_REF; otherwise CPU validation "
        "and GPU rendering will silently disagree."
    )
    assert palette_cpu[0, 0, 3] == pytest.approx(5.0, abs=1e-6)

    # Padding identities must match exactly --- a regression that
    # silently changed the upload pad would break the SSBO layout.
    for slot in range(bone_count, uploader._max_bones):
        assert upload_arr[slot, 0, 0] == pytest.approx(1.0)
        assert upload_arr[slot, 1, 1] == pytest.approx(1.0)
        assert upload_arr[slot, 2, 2] == pytest.approx(1.0)
        assert upload_arr[slot, 3, 3] == pytest.approx(1.0)
        for r in range(4):
            for c in range(4):
                if r != c:
                    assert upload_arr[slot, r, c] == pytest.approx(0.0)


def test_gpu_renderer_uploads_skin_node_local_palette() -> None:
    import inspect

    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer

    source = inspect.getsource(GpuRenderer._render_gpu)

    assert "compute_skin_node_palette(node, anim_pose)" in source
    assert "self._skin_uploader.bone_index(_bmname)" not in source


def test_cpu_skin_bind_pose_applies_node_local_transform() -> None:
    from src.gui.qt_lib.rendering.viewport_core import ArcBallCamera, FrameRenderer

    node = SimpleNamespace(
        name="body_skin",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        faces=[(0, 1, 2)],
        is_skin=True,
        is_dangly=False,
        vertex_space=0,
        bone_map=[],
        skin_data=[],
        world_transform=lambda: ((10.0, 20.0, 30.0), (0.0, 0.0, 0.0, 1.0)),
    )
    renderer = FrameRenderer(ArcBallCamera())

    assert renderer._get_world_verts_for_node(node) == [
        (11.0, 22.0, 33.0),
        (12.0, 22.0, 33.0),
        (11.0, 23.0, 33.0),
    ]


def test_non_skin_node_local_vbo_still_applies_world_transform() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_vbo_data

    node = SimpleNamespace(
        name="rigid_mesh",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        normals=[(0.0, 0.0, 1.0)] * 3,
        uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
        uvs_lm=[],
        faces=[(0, 1, 2)],
        face_uvs=[],
        is_skin=False,
        vertex_space=0,
        skin_data=[],
    )

    vbo, indices = _build_vbo_data(node, (10.0, 20.0, 30.0), (0.0, 0.0, 0.0, 1.0))

    assert indices is not None
    assert vbo is not None
    assert vbo[:, 0:3].tolist() == [
        [11.0, 22.0, 33.0],
        [12.0, 22.0, 33.0],
        [11.0, 23.0, 33.0],
    ]


def test_bonemap_overflow_slot_extends_bone_map_without_oob() -> None:
    from src.core.qt_core.game.kotor_loader import _read_skin_weights
    from src.core.qt_core.geometry.model_data import ModelNode

    id_to_node = {idx: SimpleNamespace(name=f"bone_{idx}") for idx in range(16)}
    id_to_node[99] = SimpleNamespace(name="rootdummy")
    skin = SimpleNamespace(
        bone_indices=list(range(16)),
        bonemap=list(range(16)) + [99],
        vertex_bones=[
            SimpleNamespace(vertex_indices=[16.0, -1.0, -1.0, -1.0], vertex_weights=[1.0, 0.0, 0.0, 0.0])
        ],
        qbones=[],
        tbones=[],
    )
    gr = ModelNode(name="Brith_mesh")

    _read_skin_weights(skin, gr, id_to_node)

    assert len(gr.bone_map) == 17
    assert gr.bone_map[16] == "rootdummy"
    assert len(gr.skin_data) == 1
    assert gr.skin_data[0].influences[0].bone_index == 16
    assert gr.skin_data[0].influences[0].weight == pytest.approx(1.0)


def test_quaternion_sign_equivalence_in_comparison() -> None:
    tools = pytest.importorskip("kotormcp.tools.ghostrigger_tools")

    assert tools._close_quat([0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, -1.0])
    assert tools._close_quat([0.1, 0.2, 0.3, 0.9], [-0.1, -0.2, -0.3, -0.9])
    assert not tools._close_quat([0.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.5, 0.5])


def test_is_skin_getattr_default_handles_missing_attribute() -> None:
    with_attr = SimpleNamespace(is_skin=True)
    without_attr = SimpleNamespace()

    assert bool(getattr(with_attr, "is_skin", False)) is True
    assert bool(getattr(without_attr, "is_skin", False)) is False


def test_gl_state_trace_path_is_env_gated(monkeypatch, tmp_path) -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import GpuRenderer, _gl_state_trace_path, _lm_data_dump_path, _skin_dump_path

    monkeypatch.delenv("GHOSTRIGGER_GL_STATE_TRACE", raising=False)
    monkeypatch.delenv("GHOSTRIGGER_LM_DATA_DUMP", raising=False)
    monkeypatch.delenv("GHOSTRIGGER_SKIN_DUMP", raising=False)
    assert _gl_state_trace_path() == ""
    assert GpuRenderer()._gl_state_trace_path == ""
    assert _lm_data_dump_path() == ""
    assert _skin_dump_path() == ""

    trace_path = tmp_path / "gpu_trace.jsonl"
    monkeypatch.setenv("GHOSTRIGGER_GL_STATE_TRACE", str(trace_path))

    assert _gl_state_trace_path() == str(trace_path)
    assert GpuRenderer()._gl_state_trace_path == str(trace_path)

    lm_path = tmp_path / "lm_data.jsonl"
    monkeypatch.setenv("GHOSTRIGGER_LM_DATA_DUMP", str(lm_path))

    assert _lm_data_dump_path() == str(lm_path)
    assert GpuRenderer()._lm_data_dump_path == str(lm_path)

    skin_path = tmp_path / "skin.jsonl"
    monkeypatch.setenv("GHOSTRIGGER_SKIN_DUMP", str(skin_path))

    assert _skin_dump_path() == str(skin_path)
    assert GpuRenderer()._skin_dump_path == str(skin_path)


def test_debug_visualize_mode_is_env_gated(monkeypatch) -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _debug_visualize_mode, _lm_composite_mode

    monkeypatch.delenv("GHOSTRIGGER_DEBUG_VIZ", raising=False)
    monkeypatch.delenv("GHOSTRIGGER_LM_COMPOSITE_MODE", raising=False)
    assert _debug_visualize_mode() == 0
    assert _lm_composite_mode() == 0

    monkeypatch.setenv("GHOSTRIGGER_DEBUG_VIZ", "3")
    assert _debug_visualize_mode() == 3

    monkeypatch.setenv("GHOSTRIGGER_DEBUG_VIZ", "9")
    assert _debug_visualize_mode() == 4

    monkeypatch.setenv("GHOSTRIGGER_DEBUG_VIZ", "-2")
    assert _debug_visualize_mode() == 0

    monkeypatch.setenv("GHOSTRIGGER_DEBUG_VIZ", "not-a-mode")
    assert _debug_visualize_mode() == 0

    monkeypatch.setenv("GHOSTRIGGER_LM_COMPOSITE_MODE", "2")
    assert _lm_composite_mode() == 2

    monkeypatch.setenv("GHOSTRIGGER_LM_COMPOSITE_MODE", "9")
    assert _lm_composite_mode() == 3

    monkeypatch.setenv("GHOSTRIGGER_LM_COMPOSITE_MODE", "-2")
    assert _lm_composite_mode() == 0

    monkeypatch.setenv("GHOSTRIGGER_LM_COMPOSITE_MODE", "not-a-mode")
    assert _lm_composite_mode() == 0


def test_gpu_shader_keeps_lightmap_uv_channel_independent() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _VERT_SRC

    assert "v_uv_lm  = vec2(in_uv_lm.x, 1.0 - in_uv_lm.y);" in _VERT_SRC
    assert "v_uv_lm  = vec2(in_uv_lm.x, 1.0 - in_uv.y);" not in _VERT_SRC


def test_gpu_shader_exposes_lightmap_composite_modes() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _FRAG_SRC

    assert "uniform int   u_lm_composite_mode;" in _FRAG_SRC
    assert "u_lm_composite_mode == 1" in _FRAG_SRC
    assert "diffuse_samp.rgb * lm_samp.rgb;" in _FRAG_SRC
    assert "u_lm_composite_mode == 2" in _FRAG_SRC
    assert "diffuse_samp.rgb * lm_samp.rgb * 2.0;" in _FRAG_SRC
    assert "u_lm_composite_mode == 3" in _FRAG_SRC
    assert "uniform float u_lightmap_intensity" in _FRAG_SRC
    assert "uniform int   u_lightmap_mode" in _FRAG_SRC
    assert "vec3 baked_light = mix(vec3(1.0), lm_samp.rgb * 2.0" in _FRAG_SRC
    assert "u_lightmap_mode == 2" in _FRAG_SRC
    assert "baked_light + dynamic_light" not in _FRAG_SRC


def test_gl_state_trace_record_captures_node_and_state() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_gl_state_trace_record

    ctx = SimpleNamespace(
        depth_func="<=",
        depth_mask=True,
        cull_face="back",
        front_face="cw",
        blend_func=(1, 0),
        blend_equation=32774,
    )
    uniforms = {
        "u_alpha": SimpleNamespace(value=1.0),
        "u_node_alpha": SimpleNamespace(value=0.75),
        "u_blend_mode": SimpleNamespace(value=2),
        "u_alpha_test": SimpleNamespace(value=0.5),
        "u_wateralpha": SimpleNamespace(value=1.0),
        "u_oit_enabled": SimpleNamespace(value=0),
        "u_debug_visualize": SimpleNamespace(value=0),
        "u_lm_composite_mode": SimpleNamespace(value=0),
        "u_has_tex": SimpleNamespace(value=1),
        "u_has_lm": SimpleNamespace(value=0),
        "u_has_env": SimpleNamespace(value=0),
        "u_lm_shade": SimpleNamespace(value=0),
    }
    node = SimpleNamespace(
        name="head_shell",
        transparency_hint=1,
        txi_blending=2,
        txi_alpha_test=0.5,
        txi_wateralpha=1.0,
        txi_decal=False,
        is_skin=False,
        is_dangly=False,
    )

    record = _build_gl_state_trace_record(
        ctx=ctx,
        prog=object(),
        node=node,
        pass_name="cutout",
        tri_count=12,
        blend_enabled=False,
        tex_name="headtex",
        lm_name="",
        env_name="",
        spec_name="",
        feature_mask=4096,
        uniforms=uniforms,
    )

    assert record["event"] == "draw"
    assert record["node"] == "head_shell"
    assert record["pass"] == "cutout"
    assert record["gl_depth_writemask"] is True
    assert record["gl_blend_enabled"] is False
    assert record["gl_front_face"] == "cw"
    assert record["transparency_hint"] == 1
    assert record["txi_blending"] == 2
    assert record["u_node_alpha"] == 0.75
    assert record["u_oit_enabled"] == 0
    assert record["u_debug_visualize"] == 0
    assert record["u_lm_composite_mode"] == 0
    assert record["is_face_mesh_name"] is True
    assert record["is_inner_geometry_name"] is False


def test_gl_state_trace_record_tolerates_unsupported_context_getters() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_gl_state_trace_record

    class UnsupportedDepthFunc:
        @property
        def depth_func(self):
            raise NotImplementedError()

        front_face = "cw"
        cull_face = "back"
        blend_func = (1, 0)
        blend_equation = 32774

    record = _build_gl_state_trace_record(
        ctx=UnsupportedDepthFunc(),
        prog=object(),
        node=SimpleNamespace(name="Box01"),
        pass_name="transparent",
        tri_count=1,
        blend_enabled=True,
        tex_name="",
        lm_name="",
        env_name="",
        spec_name="",
        feature_mask=0,
        uniforms={},
    )

    assert record["gl_depth_func"] is None
    assert record["gl_depth_writemask"] is False


def test_lightmap_data_dump_record_schema() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_lm_data_dump_record

    node = SimpleNamespace(
        name="mesh640",
        vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
        uvs=[(0.1, 0.2), (0.3, 0.4), (0.5, 0.6)],
        uvs_lm=[(0.11, 0.22), (0.33, 0.44), (0.55, 0.66)],
        has_lightmap=False,
        lightmap="101peras_lm0",
        tex_count=2,
        texture_names=["per_cpan", "101peras_lm0"],
        face_mats=[0, 0],
    )
    gm = SimpleNamespace(
        uploaded_vertex_count=3,
        first8_uv0_uploaded=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
        first8_uv1_uploaded=[[0.11, 0.22], [0.33, 0.44], [0.55, 0.66]],
        uv1_attribute_bound=True,
        vbo=object(),
    )
    uniforms = {
        "u_has_lm": SimpleNamespace(value=1),
        "u_lm_shade": SimpleNamespace(value=1),
        "u_lm_tex": SimpleNamespace(value=1),
        "u_debug_visualize": SimpleNamespace(value=4),
        "u_lm_composite_mode": SimpleNamespace(value=2),
    }

    record = _build_lm_data_dump_record(
        ctx=SimpleNamespace(),
        prog=object(),
        node=node,
        pass_name="opaque",
        gm=gm,
        has_lm_flag=True,
        lightmap_bound=True,
        lm_img=None,
        lm_name="101peras_lm0",
        uniforms=uniforms,
    )

    assert record["event"] == "lightmap_draw"
    assert record["node"] == "mesh640"
    assert record["vertex_count"] == 3
    assert record["uploaded_vertex_count"] == 3
    assert record["len_uvs"] == 3
    assert record["len_uvs_lm"] == 3
    assert record["first8_uv1_model"][0] == [0.11, 0.22]
    assert record["first8_uv1_uploaded"][0] == [0.11, 0.22]
    assert record["lightmap_role_inferred"] is True
    assert record["dispatch_path"] == "Case A"
    assert record["slot1_role"] == "lightmap"
    assert record["lightmap_texture_name"] == "101peras_lm0"
    assert record["lightmap_texture_stats"] is None
    assert record["lightmap_bound"] is True
    assert record["uv1_attribute_bound"] is True
    assert record["lightmap_uniforms"]["u_lm_shade"] == 1
    assert record["lightmap_uniforms"]["u_lm_composite_mode"] == 2


def test_skin_dump_record_schema() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_skin_dump_record

    node = SimpleNamespace(
        name="SkinMesh",
        is_skin=True,
        is_dangly=False,
        vertices=[(1.0, 2.0, 3.0)],
        bone_map=["Root", "Arm"],
        skin_data=[
            SimpleNamespace(influences=[
                SimpleNamespace(bone_index=1, weight=0.75),
                SimpleNamespace(bone_index=0, weight=0.25),
            ])
        ],
    )
    root = SimpleNamespace(name="Root", position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0))
    arm = SimpleNamespace(name="Arm", position=(1.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0))
    model = SimpleNamespace(
        name="TestModel",
        find_node=lambda name: {"Root": root, "Arm": arm}.get(name),
    )
    uploader = SimpleNamespace(
        bone_count=2,
        _inv_bind={"root": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
                   "arm": [[1, 0, 0, -1], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
        _inv_bind_anim=None,
        _skin_palette_formula="F1_current_TR_inverse",
        _skin_inverse_bind_source="qBone_tBone_inverse_TR",
        _skin_bind_matrix=[[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        as_numpy_array=lambda: None,
        as_flat_bytes=lambda: b"",
    )
    uniforms = {
        "u_skin_enabled": SimpleNamespace(value=1),
        "u_bone_count": SimpleNamespace(value=2),
    }

    record = _build_skin_dump_record(
        model=model,
        node=node,
        pass_name="opaque",
        uploader=uploader,
        bone_remap={0: 0, 1: 1},
        uniforms=uniforms,
        anim_pose=None,
        anim_base_pose=None,
        anim_time=0.5,
    )

    assert record["event"] == "skin_draw"
    assert record["node"] == "SkinMesh"
    assert record["is_skin"] is True
    assert record["is_dangly"] is False
    assert record["bone_map"] == ["Root", "Arm"]
    assert record["selected_vertex"]["index"] == 0
    assert record["selected_vertex"]["influences"][0]["local_bone_index"] == 1
    assert record["referenced_bones"][0]["bone_name"] == "Arm"
    assert record["referenced_bones"][0]["palette_index"] == 1
    assert record["u_skin_enabled"] == 1
    assert record["u_bone_count"] == 2
    assert record["shader_bone_ids_type"] == "ivec4"
    assert record["bone_ids_attribute_format"] == "4i"
    assert record["live_local_indices"] == [0, 1]
    assert record["live_empty_bone_slots"] == []
    assert record["live_slots"][1]["bone_name"] == "Arm"
    assert record["live_slots"][1]["palette_index"] == 1
    assert "qbone_inverse_bind_matrix" in record["live_slots"][1]
    assert "inverse_bind_vs_qbone_max_abs" in record["live_slots"][1]
    assert record["skin_transform_formula"] == "F1_current_TR_inverse"
    assert record["skin_bind_present"] is True
    assert record["skin_bind_det"] == 1.0
    assert record["skin_bind_equivalence"]["reference_renderer"] == "KotOR.js/Three.js"
    assert "kotorjs_default_mesh_matrixWorld" in record["skin_bind_equivalence"]["candidate_matrices"]
    assert "candidate_vs_current_max_abs" in record["skin_bind_equivalence"]
    assert "pre_qbone_basis_provenance_summary" in record
    summary = record["pre_qbone_basis_provenance_summary"]
    assert summary["loader_pretransform"] in {
        "none_passthrough_proven_by_raw_equals_vbo",
        "pretransform_detected_per_probe",
        "no_probes_available",
    }
    assert "ghostrigger_skin_bind_composition" in summary
    assert "reference_pre_wrapper_transform_composition" in summary
    assert "classification" in summary
    assert "recommended_next_audit" in summary
    assert "step7_b_translation_summary" in record
    step7 = record["step7_b_translation_summary"]
    assert step7["f11_outer_composition"] == "rotation_only_skin_bind"
    assert step7["f12_outer_composition"].startswith("xoreos_first_frame_orientation_chain")
    assert "classification" in step7
    assert "visual_gate_recommendation" in step7
    assert record["bone_inverse_bind_source"] == "qBone_tBone_inverse_TR"
    assert "palette_matrix_preupload_first_live_slot" in record
    assert "palette_matrix_uploaded_first_live_slot" in record
    assert "F1_current_TR_inverse" in record["skin_transform_convention_formulas"]
    assert "F9_xoreos_TR_direct_wrapper" in record["skin_transform_convention_formulas"]
    assert "skin_transform_convention_probes" in record


def test_skin_dump_records_live_empty_bone_slots() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_skin_dump_record

    node = SimpleNamespace(
        name="SkinMesh",
        is_skin=True,
        is_dangly=False,
        vertices=[(1.0, 2.0, 3.0)],
        bone_map=["Root", ""],
        skin_data=[
            SimpleNamespace(influences=[
                SimpleNamespace(bone_index=1, weight=1.0),
            ])
        ],
    )
    model = SimpleNamespace(
        name="TestModel",
        root_node=SimpleNamespace(name="Root"),
        find_node=lambda name: None,
    )
    uploader = SimpleNamespace(
        bone_count=2,
        _inv_bind={},
        _inv_bind_anim=None,
        as_numpy_array=lambda: None,
        as_flat_bytes=lambda: b"",
    )

    record = _build_skin_dump_record(
        model=model,
        node=node,
        pass_name="opaque",
        uploader=uploader,
        bone_remap={0: 0, 1: 0},
        uniforms={},
        anim_pose=None,
        anim_base_pose=None,
        anim_time=0.0,
    )

    assert record["live_empty_bone_slots"] == [1]
    assert record["live_slots"][0]["bone_name"] == ""
    assert record["live_slots"][0]["palette_index"] == 0


def test_skin_dump_records_3g_candidate_formula_probe() -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _build_skin_dump_record

    head = SimpleNamespace(
        name="head_g",
        parent=None,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
    )
    node = SimpleNamespace(
        name="headGeo",
        parent=None,
        is_skin=True,
        is_dangly=False,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        vertices=[(1.0, 2.0, 3.0)],
        bone_map=["head_g"],
        qbone_list=[(0.0, 0.0, 0.0, 1.0)],
        tbone_list=[(0.0, 0.0, 0.0)],
        skin_data=[
            SimpleNamespace(influences=[
                SimpleNamespace(bone_index=0, weight=1.0),
            ])
        ],
    )
    model = SimpleNamespace(
        name="C_DrexlF",
        root_node=SimpleNamespace(name="C_DrexlF"),
        find_node=lambda name: {"head_g": head}.get(name),
        all_nodes=lambda: [head, node],
    )
    uploader = SimpleNamespace(
        bone_count=1,
        _inv_bind={"head_g": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
        _inv_bind_anim=None,
        _skin_local_inv_bind_by_slot={0: [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]},
        as_numpy_array=lambda: None,
        as_flat_bytes=lambda: b"",
    )

    record = _build_skin_dump_record(
        model=model,
        node=node,
        pass_name="opaque",
        uploader=uploader,
        bone_remap=None,
        uniforms={},
        anim_pose=None,
        anim_base_pose=None,
        anim_time=0.0,
    )

    probes = record["skin_transform_convention_probes"]
    assert probes[0]["vertex_role"] == "head"
    assert probes[0]["vertex_index"] == 0
    assert probes[0]["raw_position"] == [1.0, 2.0, 3.0]
    assert probes[0]["raw_mdx_position"] == [1.0, 2.0, 3.0]
    assert probes[0]["vbo_in_pos"] == [1.0, 2.0, 3.0]
    assert probes[0]["vbo_source_vertex_index"] == 0
    assert probes[0]["raw_vs_vbo_max_abs"] == 0.0
    assert probes[0]["interpreted_raw_space"] == "skin_node_vbo_input_space"
    assert probes[0]["influences"][0]["parent_chain"] == ["head_g"]
    assert probes[0]["influences"][0]["animated_world_chain"][0]["node_name"] == "head_g"
    assert "production_per_bone_position_from_vbo_in_pos" in probes[0]["influences"][0]
    assert "production_replay_pre_weight_positions" in probes[0]
    assert "reference_f8_replay_pre_weight_positions" in probes[0]
    assert "reference_f9_replay_pre_weight_positions" in probes[0]
    assert "production_weighted_sum_position" in probes[0]
    assert "reference_f8_weighted_sum_position" in probes[0]
    assert "skin_bind_applied_position" in probes[0]
    assert "skin_unbind_applied_position" in probes[0]
    assert "animated_world_applied_position" in probes[0]
    assert "first_divergence_stage" in probes[0]
    assert "first_post_skin_bind_mismatch_stage_reference_f8" in probes[0]
    assert "qbone_already_raw_basis_probe_weighted_sum_position" in probes[0]
    assert "raw_after_skin_bind_position" in probes[0]
    assert "reference_pre_qbone_input_position" in probes[0]
    assert "production_pre_qbone_input_position" in probes[0]
    assert "reference_pre_qbone_vs_production_vbo_max_abs" in probes[0]
    assert "skin_bind_moves_raw_max_abs" in probes[0]
    provenance = probes[0]["pre_qbone_basis_provenance"]
    assert provenance["loader_pretransform_detected"] == "none_passthrough"
    assert "skin_bind_translation_norm" in provenance
    assert "reference_pre_qbone_with_rotation_only_skin_bind_position" in provenance
    assert "reference_pre_qbone_with_rotation_only_vs_production_vbo_max_abs" in provenance
    assert "inverse_skin_bind_times_vbo_position" in provenance
    assert "inverse_skin_bind_times_vbo_vs_raw_max_abs" in provenance
    assert "F1_current_TR_inverse" in probes[0]["candidate_formula_positions"]
    assert "F5_skin_bind_precancel" in probes[0]["candidate_distance_from_raw"]
    assert "F9_xoreos_TR_direct_wrapper" in probes[0]["candidate_formula_positions"]
    assert "F11_rotation_only_skin_bind_wrapper" in probes[0]["candidate_formula_positions"]
    assert "F12_xoreos_first_frame_orientation_wrapper" in probes[0]["candidate_formula_positions"]
    step7_probe = probes[0]["step7_b_translation"]
    assert step7_probe["f11_outer_composition"] == "rotation_only_skin_bind"
    assert "f11_collapses_to_production" in step7_probe
    assert "f12_collapses_to_production" in step7_probe
    assert "step7_interpretation" in step7_probe
    assert "H1_raw_as_mesh_space" in probes[0]["raw_vertex_space_candidate_positions"]
    assert "H2_raw_as_skin_node_local" in probes[0]["raw_vertex_space_distance_from_raw"]
    assert "gpu_skinned_position_after_3g_fix" in probes[0]


def test_gl_context_backend_candidates_are_platform_aware(monkeypatch) -> None:
    from src.gui.qt_lib.rendering.gpu_renderer import _gl_context_backend_candidates

    monkeypatch.delenv("GHOSTRIGGER_GL_BACKEND", raising=False)

    assert _gl_context_backend_candidates("nt")[:2] == ("default", "wgl")
    assert _gl_context_backend_candidates("posix")[:2] == ("egl", "default")
    assert _gl_context_backend_candidates("java") == ("default",)

    monkeypatch.setenv("GHOSTRIGGER_GL_BACKEND", "wgl")

    assert _gl_context_backend_candidates("posix") == ("wgl",)


def test_resource_manager_indexes_override_without_preloading(tmp_path) -> None:
    from src.core.qt_core.assets.resource_manager import RES_TPC, _GameInstall, _key

    override = tmp_path / "Override"
    override.mkdir()
    texture = override / "sample.tpc"
    texture.write_bytes(b"texture-bytes")

    inst = _GameInstall.__new__(_GameInstall)
    inst.game_dir = str(tmp_path)
    inst.tag = "TEST"
    inst._override = {}

    _GameInstall._load_override(inst)

    key = _key("sample", RES_TPC)
    assert inst._override[key] == str(texture)
    assert inst.get("sample", RES_TPC) == b"texture-bytes"


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_k2_rgba_lightmap_decode_is_not_dxt_noise() -> None:
    from PIL import ImageStat

    from src.core.qt_core.game.kotor_loader import patch_tpc_header
    from src.core.qt_core.assets.resource_manager import RES_TPC, _decode_texture

    manager = _resource_manager()
    raw = manager.get("101peras_lm0", RES_TPC, "K2")
    assert raw is not None

    assert patch_tpc_header(raw) == raw
    img = _decode_texture(raw)
    assert img is not None

    mean_rgb = ImageStat.Stat(img.convert("RGB")).mean
    assert all(5.0 <= channel <= 90.0 for channel in mean_rgb)


@pytest.mark.skipif(not K1_PATH.exists(), reason="K1 install not available")
def test_k1_lightmap_decode_controls_remain_stable() -> None:
    from PIL import ImageStat

    from src.core.qt_core.assets.resource_manager import RES_TGA, RES_TPC, _decode_texture

    manager = _resource_manager()
    baselines = {
        "m03aa_05a_lm0": (53.9253, 49.6870, 52.6313),
        "m02aa_01a_lm0": (60.2322, 63.7241, 69.4634),
    }

    for name, expected in baselines.items():
        raw = manager.get(name, RES_TPC, "K1") or manager.get(name, RES_TGA, "K1")
        assert raw is not None
        img = _decode_texture(raw)
        assert img is not None
        mean_rgb = ImageStat.Stat(img.convert("RGB")).mean
        for actual, target in zip(mean_rgb, expected):
            assert actual == pytest.approx(target, abs=2.0)


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_k2_rgba_lightmap_txi_starts_at_clean_boundary(caplog) -> None:
    import logging

    from src.core.qt_core.assets.resource_manager import RES_TPC, _tpc_uncompressed_txi
    from src.gui.qt_lib.rendering.viewport_core import _parse_txi_string

    manager = _resource_manager()
    raw = manager.get("101peras_lm0", RES_TPC, "K2")
    assert raw is not None

    txi = _tpc_uncompressed_txi(raw)
    assert txi.splitlines()[0] == "islightmap 1"

    with caplog.at_level(logging.WARNING):
        parsed = _parse_txi_string(txi)

    assert parsed["islightmap"] is True
    assert not [record for record in caplog.records if "Invalid TXI command" in record.message]


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_owned_reader_handles_k2_mdx_offset_zero() -> None:
    reader, model = _reader_for("k2", "c_brith")
    nodes = _nodes_by_name(model)

    zero_nodes = [
        bin_node for bin_node in reader._gr_bin_nodes.values()
        if bin_node.trimesh is not None
        and bin_node.trimesh.vertex_count > 0
        and bin_node.trimesh.mdx_data_offset == 0
    ]

    assert zero_nodes, "Expected at least one K2 mesh with mdx_data_offset == 0"
    for bin_node in zero_nodes:
        name = reader._names[bin_node.header.node_id].lower()
        node = nodes.get(name)
        assert node is not None, f"Loaded model missing node {name!r}"
        assert len(node.mesh.vertex_positions) == bin_node.trimesh.vertex_count


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_owned_reader_handles_k2_nonzero_mdx_offsets() -> None:
    reader, model = _reader_for("k2", "101perd")
    nodes = _nodes_by_name(model)

    nonzero_nodes = [
        bin_node for bin_node in reader._gr_bin_nodes.values()
        if bin_node.trimesh is not None
        and bin_node.trimesh.vertex_count > 0
        and bin_node.trimesh.mdx_data_offset not in (0, 0xFFFFFFFF)
    ]

    assert nonzero_nodes, "Expected at least one K2 mesh with nonzero MDX offset"
    for bin_node in nonzero_nodes[:3]:
        name = reader._names[bin_node.header.node_id].lower()
        node = nodes.get(name)
        assert node is not None, f"Loaded model missing node {name!r}"
        assert len(node.mesh.vertex_positions) == bin_node.trimesh.vertex_count


@pytest.mark.skipif(not K1_PATH.exists(), reason="K1 install not available")
def test_read_mdl_safe_k1_control_model() -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    mdl, mdx = _raw_model("k1", "m03aa_05a")
    model = read_mdl_safe(mdl, source_ext=mdx)

    assert model.name.lower() == "m03aa_05a"
    assert len(model.all_nodes()) == 24
    assert any(node.mesh and node.mesh.vertex_positions for node in model.all_nodes())


@pytest.mark.skipif(not K1_PATH.exists(), reason="K1 install not available")
def test_read_mdl_safe_k1_supermodel_node_order_uses_logical_offsets() -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    mdl, mdx = _raw_model("k1", "s_male02")
    model = read_mdl_safe(mdl, source_ext=mdx)

    assert model.name.lower() == "s_male02"
    node_names = [node.name.lower() for node in model.all_nodes()]
    assert len(node_names) >= 80
    assert "impact_bolt" in node_names
    assert len(model.anims) == 166


@pytest.mark.parametrize(
    ("game", "resref", "expected_node"),
    [
        ("k1", "fx_explode_03", "auroralight04"),
        ("k2", "504ondh", "sunaurora"),
    ],
)
def test_read_mdl_safe_trims_stock_light_arrays(game: str, resref: str, expected_node: str) -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    mdl, mdx = _raw_model(game, resref)
    model = read_mdl_safe(mdl, source_ext=mdx)

    node_names = {node.name.lower() for node in model.all_nodes()}
    assert expected_node in node_names


@pytest.mark.skipif(not K1_PATH.exists(), reason="K1 install not available")
def test_read_mdl_safe_sanitizes_stock_nan_face_coefficients() -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    mdl, mdx = _raw_model("k1", "w_dblsbr_001")
    model = read_mdl_safe(mdl, source_ext=mdx)
    mesh_nodes = [node for node in model.all_nodes() if node.mesh is not None]

    assert any(node.name.lower() == "dblsbr" for node in mesh_nodes)
    assert all(isinstance(face.coefficient, int) for node in mesh_nodes for face in node.mesh.faces)


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_read_mdl_safe_does_not_require_source_inspection(monkeypatch) -> None:
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    def _raise_oserror(_obj):
        raise OSError("could not get source code")

    monkeypatch.setattr(inspect, "getsource", _raise_oserror)
    mdl, mdx = _raw_model("k2", "c_brith")
    model = read_mdl_safe(mdl, source_ext=mdx)

    assert model.name.lower() == "c_brith"
    assert any(node.skin and node.mesh.vertex_positions for node in model.all_nodes())


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_read_mdl_safe_does_not_activate_pykotor_patch_bridge(monkeypatch) -> None:
    from src.core.qt_core.game import pykotor_mdl_io_fix as fix
    from src.core.qt_core.mdl.mdl_reader_wrapper import read_mdl_safe

    monkeypatch.setattr(fix, "_applied", False)
    mdl, mdx = _raw_model("k2", "c_brith")

    model = read_mdl_safe(mdl, source_ext=mdx)

    assert model.name.lower() == "c_brith"
    assert fix._applied is False


@pytest.mark.skipif(not K2_PATH.exists(), reason="K2 install not available")
def test_c_drexlf_texture_alias_resolves_shipped_diffuse() -> None:
    from src.core.qt_core.game.kotor_loader import load_model_from_bytes
    from src.core.qt_core.assets.resource_manager import resolve_model_textures

    manager = _resource_manager()
    authored = manager.get_texture("c_drex01", "K2")
    shipped = manager.get_texture("c_drexl01", "K2")

    assert authored is not None
    assert shipped is not None
    assert authored == shipped

    mdl, mdx = _raw_model("k2", "c_drexlf")
    model = load_model_from_bytes(mdl, mdx)
    textures = resolve_model_textures(model, manager=manager, game="K2")

    assert "c_drex01" in textures


@pytest.mark.skipif(not K1_PATH.exists(), reason="K1 install not available")
def test_k1_aurora_light_controllers_populate_runtime_light_fields() -> None:
    from src.core.qt_core.game.kotor_loader import load_model_from_bytes

    mdl, mdx = _raw_model("k1", "m01aa_04a")
    model = load_model_from_bytes(mdl, mdx)
    lights = {node.name: node for node in model.all_nodes() if node.is_light}

    light = lights["AuroraLight254"]
    assert light.light_radius == pytest.approx(12.0)
    assert light.light_multiplier == pytest.approx(2.0)
    assert light.light_color == pytest.approx((0.921571, 0.964708, 1.0))
    assert light.light_kind == "point"
    assert light.light_enabled is True
