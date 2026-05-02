from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_bug_c_composite_offset_applies_to_skin_nodes() -> None:
    from src.gui.gpu_renderer import _build_vbo_data

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


def test_skin_bind_pose_vbo_keeps_authored_coordinates() -> None:
    from src.gui.gpu_renderer import _build_vbo_data

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
        [1.0, 2.0, 3.0],
        [2.0, 2.0, 3.0],
        [1.0, 3.0, 3.0],
    ]


def test_cpu_skin_bind_pose_keeps_authored_coordinates() -> None:
    from src.gui.viewport import ArcBallCamera, FrameRenderer

    node = SimpleNamespace(
        name="body_skin",
        vertices=[(1.0, 2.0, 3.0), (2.0, 2.0, 3.0), (1.0, 3.0, 3.0)],
        faces=[(0, 1, 2)],
        is_skin=True,
        is_dangly=False,
        vertex_space=0,
        bone_map=[],
        skin_data=[],
        world_transform=lambda: ((10.0, 20.0, 30.0), (0.0, 0.0, 1.0, 0.0)),
    )
    renderer = FrameRenderer(ArcBallCamera())

    assert renderer._get_world_verts_for_node(node) == [
        (1.0, 2.0, 3.0),
        (2.0, 2.0, 3.0),
        (1.0, 3.0, 3.0),
    ]


def test_non_skin_node_local_vbo_still_applies_world_transform() -> None:
    from src.gui.gpu_renderer import _build_vbo_data

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
    from src.core.kotor_loader import _read_skin_weights
    from src.core.model_data import ModelNode

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
