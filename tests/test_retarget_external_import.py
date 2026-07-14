"""Regression tests for Retarget Workbench external-file import routing."""

from __future__ import annotations

import importlib.util
import inspect
import math
import os
import pathlib
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _load_native_python_module(module_name: str, relative_path: str):
    path = pathlib.Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _sample_clip(
    *,
    child_local_position: tuple[float, float, float] = (1.0, 0.0, 0.0),
    child_global_position: tuple[float, float, float] = (1.0, 0.0, 0.0),
    root_rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
    extra_nodes: list | None = None,
):
    from src.core.retargeting.source_animation import (
        SourcePose,
        SourceSkeletonClip,
        SourceSkeletonNode,
        Transform,
    )

    root_local = Transform(rotation=root_rotation)
    child_local = Transform(position=child_local_position)
    root_global = Transform(rotation=root_rotation)
    child_global = Transform(position=child_global_position)
    nodes = [
        SourceSkeletonNode("Root", None, 0, root_local, root_global),
        SourceSkeletonNode("RHand", "Root", 1, child_local, child_global),
    ]
    if extra_nodes:
        nodes.extend(extra_nodes)
    pose = SourcePose(
        time_seconds=0.0,
        local_transforms={node.name: node.rest_local for node in nodes},
        global_transforms={node.name: node.rest_global for node in nodes},
    )
    return SourceSkeletonClip(
        source_path="demo.fbx",
        clip_name="root|Unreal Take|Base Layer",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
        axis_system="blender_fbx_import_z_up",
        available_clips=[
            {"name": "root|Unreal Take|Base Layer", "duration_seconds": 1.0, "frame_start": 0.0, "frame_end": 30.0},
        ],
    )


def test_mesh_converter_imports_without_legacy_top_level_core_package() -> None:
    sys.modules.pop("core", None)

    from src.converters.mesh_converter import FBXImporter, KotorModel

    assert FBXImporter.__name__ == "FBXImporter"
    assert KotorModel.__module__ == "src.core.geometry.model_data"


def test_unreal_source_fbx_import_routes_to_source_clip_before_mesh_conversion() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_import_external_model)

    fbx_source_route = 'role == "source" and suffix == ".fbx" and controller is not None and mode_name == "UNREAL_TO_KOTOR"'
    assert fbx_source_route in source
    assert "controller.load_source_clip(path)" in source
    assert "import_fbx_mesh_with_blender" in source
    assert "find_mixamo_companion_mesh_path" in source
    assert "configured_mesh_path=self.settings_data.get(\"mixamo_companion_mesh_path\")" in source
    assert "self.settings_data[\"mixamo_companion_mesh_path\"]" in source
    assert "window.set_source_clip_preview(clip, mesh_model=mesh_model)" in source
    assert source.index(fbx_source_route) < source.index("model = self._load_external_retarget_model(path)")


def test_mixamo_companion_mesh_finder_uses_sibling_x_bot(tmp_path) -> None:
    from src.core.retargeting.mixamo_companion_mesh import find_mixamo_companion_mesh_path

    animation = tmp_path / "draw sword 1.fbx"
    companion = tmp_path / "X Bot.fbx"
    animation.write_bytes(b"anim")
    companion.write_bytes(b"mesh")
    bones = [
        "mixamorig:Hips",
        "mixamorig:Spine",
        "mixamorig:Spine1",
        "mixamorig:Spine2",
        "mixamorig:LeftArm",
        "mixamorig:RightArm",
        "mixamorig:LeftUpLeg",
        "mixamorig:RightUpLeg",
    ]

    assert find_mixamo_companion_mesh_path(animation, bones) == companion


def test_mixamo_companion_mesh_finder_prefers_remembered_x_bot(tmp_path) -> None:
    from src.core.retargeting.mixamo_companion_mesh import find_mixamo_companion_mesh_path

    anim_dir = tmp_path / "anims"
    mesh_dir = tmp_path / "native"
    anim_dir.mkdir()
    mesh_dir.mkdir()
    animation = anim_dir / "sword and shield attack.fbx"
    sibling = anim_dir / "X Bot.fbx"
    remembered = mesh_dir / "X Bot.fbx"
    animation.write_bytes(b"anim")
    sibling.write_bytes(b"sibling")
    remembered.write_bytes(b"remembered")
    bones = [
        "mixamorig:Hips",
        "mixamorig:Spine",
        "mixamorig:Spine1",
        "mixamorig:Spine2",
        "mixamorig:LeftArm",
        "mixamorig:RightArm",
        "mixamorig:LeftUpLeg",
        "mixamorig:RightUpLeg",
    ]

    assert find_mixamo_companion_mesh_path(
        animation,
        bones,
        configured_mesh_path=remembered,
    ) == remembered


def test_mixamo_companion_mesh_finder_ignores_non_mixamo(tmp_path) -> None:
    from src.core.retargeting.mixamo_companion_mesh import find_mixamo_companion_mesh_path

    animation = tmp_path / "run.fbx"
    companion = tmp_path / "X Bot.fbx"
    animation.write_bytes(b"anim")
    companion.write_bytes(b"mesh")

    assert find_mixamo_companion_mesh_path(animation, ["pelvis", "spine_01", "upperarm_l"]) is None


def test_kotor_to_unreal_target_fbx_import_routes_to_unreal_skeleton_before_mesh_conversion() -> None:
    from src.gui.qt_lib.windows.qt_main_window import QtGhostRiggerMainWindow

    source = inspect.getsource(QtGhostRiggerMainWindow._retarget_import_external_model)

    fbx_target_route = 'role == "target" and suffix == ".fbx" and controller is not None and mode_name == "KOTOR_TO_UNREAL"'
    assert fbx_target_route in source
    assert "controller.set_target_unreal_skeleton(import_unreal_target_skeleton_from_fbx(path))" in source
    assert source.index(fbx_target_route) < source.index("model = self._load_external_retarget_model(path)")


def test_source_clip_preview_model_preserves_imported_skeleton_for_viewport() -> None:
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model
    from src.core.retargeting.source_animation import SourceSkeletonNode, Transform

    model = build_source_clip_preview_model(
        _sample_clip(
            extra_nodes=[
                SourceSkeletonNode("upperarm_twist_01_l", "Root", 2, Transform(), Transform(), "twist"),
                SourceSkeletonNode("ik_foot_root", "Root", 3, Transform(), Transform(), "ik"),
                SourceSkeletonNode("weapon_socket", "Root", 4, Transform(), Transform(), "helper"),
            ]
        )
    )

    assert model.name == "root|Unreal Take|Base Layer"
    assert model.node_count() == 6
    assert getattr(model, "_gr_source_clip_preview") is True
    assert getattr(model, "_gr_source_clip_node_count") == 5
    assert [anim.name for anim in model.animations] == ["root|Unreal Take|Base Layer"]
    assert model.animations[0].length == 1.0
    assert [node.name for node in model.root_node.children] == ["Root"]
    root = model.root_node.children[0]
    assert {node.name for node in root.children} == {"RHand", "upperarm_twist_01_l", "ik_foot_root", "weapon_socket"}
    rhand = next(node for node in root.children if node.name == "RHand")
    assert getattr(rhand, "external_world_position") == (1.0, 0.0, 0.0)
    assert getattr(rhand, "_gr_source_clip_preview_position") == (1.0, 0.0, 0.0)
    hidden = {node.name for node in model.all_nodes() if getattr(node, "_hide_skeleton_overlay", False)}
    assert hidden == {"upperarm_twist_01_l", "ik_foot_root", "weapon_socket"}
    bb_min, bb_max = getattr(model, "_gr_render_bounds")
    assert bb_min[0] < bb_max[0]
    assert bb_min[1] < bb_max[1]
    assert bb_min[2] < bb_max[2]


def test_source_clip_preview_model_derives_parent_local_offsets_from_global_pose() -> None:
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    model = build_source_clip_preview_model(
        _sample_clip(
            child_local_position=(100.0, 0.0, 0.0),
            child_global_position=(0.0, 1.0, 0.0),
            root_rotation=(0.0, 0.0, 0.70710678, 0.70710678),
        )
    )

    root = model.find_node("Root")
    rhand = model.find_node("RHand")

    assert root is not None
    assert rhand is not None
    assert root.rotation == pytest.approx((0.0, 0.0, 0.70710678, 0.70710678))
    assert rhand.position == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)
    assert getattr(rhand, "_gr_source_clip_preview_position") == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)


def test_source_clip_preview_model_can_include_fbx_mesh_geometry() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.geometry.model_data import GameVersion
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    mesh_model = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["root"],
            "actions": [{"name": "root|Unreal Take|Base Layer"}],
            "meshes": [
                {
                    "name": "Body",
                    "vertices": [[-1, 0, 0], [1, 0, 0], [0, 0, 2]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0, 0], [1, 0], [0.5, 1]],
                    "faces": [[0, 1, 2]],
                    "materials": [{"name": "BodyMat", "texture": "Body_D", "diffuse": [0.5, 0.6, 0.7]}],
                }
            ],
        },
        model_name="source_body",
        game_version=GameVersion.K1,
    )

    model = build_source_clip_preview_model(_sample_clip(), mesh_model=mesh_model)
    mesh_nodes = [node for node in model.all_nodes() if getattr(node, "_gr_fbx_mesh_preview_node", False)]

    assert getattr(model, "_gr_source_clip_preview") is True
    assert getattr(model, "_gr_source_clip_mesh_count") == 1
    assert mesh_model.metadata["external_import"]["disable_kotor_uv_seam_fix"] is True
    assert len(mesh_nodes) == 1
    assert mesh_nodes[0].name == "Body"
    assert mesh_nodes[0].texture == "Body_D"
    assert getattr(mesh_nodes[0], "_external_imported", False) is True
    assert getattr(mesh_nodes[0], "uv_v_flip", True) is False
    assert mesh_nodes[0].vertex_space == 1
    assert mesh_nodes[0].vertices
    assert mesh_nodes[0].uvs == pytest.approx([(0, 0), (1, 0), (0.5, 1)])
    assert mesh_nodes[0].faces == [(0, 1, 2)]


def test_blender_fbx_preview_meshes_keep_dcc_uv_convention_for_viewport() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.geometry.model_data import GameVersion
    from src.core.rendering.mesh_render_data import _node_uv_array

    mesh_model = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["Armature"],
            "meshes": [
                {
                    "name": "Bendak",
                    "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0.125, 0.25], [0.875, 0.5], [0.25, 0.75]],
                    "faces": [[0, 1, 2]],
                    "materials": [
                        {
                            "name": "Bendak",
                            "texture": "BendakStarkiller_basecolor",
                            "diffuse": [0.8, 0.8, 0.8],
                        }
                    ],
                }
            ],
        },
        model_name="Bendak",
        game_version=GameVersion.K1,
    )

    mesh_node = next(node for node in mesh_model.all_nodes() if getattr(node, "vertices", None))

    assert getattr(mesh_node, "_external_imported", False) is True
    assert getattr(mesh_node, "uv_v_flip", True) is False
    assert mesh_node.uvs == pytest.approx([(0.125, 0.25), (0.875, 0.5), (0.25, 0.75)])
    assert _node_uv_array(mesh_node, "uvs", 3).reshape(-1).tolist() == pytest.approx(
        [0.125, 0.75, 0.875, 0.5, 0.25, 0.25]
    )


def test_blender_fbx_mesh_payload_preserves_armature_guides_for_autofit() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.characters.headless_body_workflow import inspect_external_model_fit
    from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode, NodeFlags

    source = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["Armature"],
            "armature_objects": [
                {
                    "name": "Armature",
                    "bones": [
                        {"name": "Hips", "parent": None, "world_position": [0.0, 0.0, 0.0]},
                        {"name": "Head", "parent": "Hips", "world_position": [0.0, -10.0, 0.0]},
                        {"name": "LeftShoulder", "parent": "Hips", "world_position": [-1.0, -8.0, 0.0]},
                        {"name": "RightShoulder", "parent": "Hips", "world_position": [1.0, -8.0, 0.0]},
                        {"name": "LeftFoot", "parent": "Hips", "world_position": [-0.4, 0.0, -0.1]},
                        {"name": "RightFoot", "parent": "Hips", "world_position": [0.4, 0.0, -0.1]},
                    ],
                }
            ],
            "actions": [{"name": "Armature|Take|Base Layer"}],
            "meshes": [
                {
                    "name": "Head",
                    "vertices": [[-0.2, 0.0, 99.0], [0.2, 0.0, 100.0], [0.0, 0.2, 101.0]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0, 0], [1, 0], [0.5, 1]],
                    "faces": [[0, 1, 2]],
                    "materials": [{"name": "BodyMat", "texture": "Body_D", "diffuse": [0.5, 0.6, 0.7]}],
                }
            ],
        },
        model_name="bendak_payload",
        game_version=GameVersion.K1,
    )

    guide_nodes = [
        node for node in source.all_nodes()
        if getattr(node, "_gr_imported_armature_joint", False)
    ]
    assert getattr(source, "_gr_fbx_armature_bone_count") == 6
    assert {node.name for node in guide_nodes} == {
        "Hips",
        "Head",
        "LeftShoulder",
        "RightShoulder",
        "LeftFoot",
        "RightFoot",
    }
    assert next(node for node in guide_nodes if node.name == "Head").external_world_position == pytest.approx((0.0, 0.0, 10.0))

    reference = KotorModel(name="n_mandalorian", game_version=GameVersion.K1)
    root = ModelNode(name="n_mandalorian", flags=int(NodeFlags.HEADER))
    reference.root_node = root
    for name, pos in [
        ("pelvis_g", (0.0, 0.0, 0.8)),
        ("head_g", (0.0, 0.0, 1.6)),
        ("lcollar_g", (-0.4, 0.0, 1.25)),
        ("rcollar_g", (0.4, 0.0, 1.25)),
        ("lfoot_g", (-0.2, 0.0, 0.0)),
        ("rfoot_g", (0.2, 0.0, 0.0)),
    ]:
        node = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=root)
        node.position = pos
        root.children.append(node)
    reference.compute_bounds()

    report = inspect_external_model_fit(
        source,
        game_version="K1",
        reference_model=reference,
        reference_label="n_mandalorian",
    )

    assert report["fit_policy"] == "bone_landmark_basis"
    assert report["source_imported_armature"] == {
        "source": "imported_fbx_armature",
        "guide_joint_count": 6,
        "scene_guide_joint_count": 6,
        "armature_names": ["Armature"],
    }
    assert report["source_frame"]["landmarks"]["head"] == "Head"
    assert report["source_frame"]["landmark_sources"]["head"] == "imported_skeleton"
    assert report["source_frame"]["landmark_sources"]["pelvis"] == "imported_skeleton"
    assert report["source_height"] == pytest.approx(10.0)
    assert report["fit_transform"]["landmark_alignment"]["pair_count"] == 6
    assert "Imported skeleton landmarks drove orientation and scale" in report["auto_fit_report"]["notes"]


def test_kotor_space_creature_replacement_keeps_identity_fit() -> None:
    from src.core.characters.headless_body_workflow import normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source.metadata = {
        "external_import": {
            "source_path": r"C:\mods\C_DrexlF_UV.fbx",
            "target_axis_system": "kotor_z_up",
            "axis_conversion": "blender_xyz_to_kotor_xz_minus_y",
        }
    }
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    native_min = (-4.3794, -5.9490, 0.9094)
    native_max = (4.4521, 2.1383, 2.7630)
    source_mesh.vertices = [
        (x, y, z)
        for x in (native_min[0], native_max[0])
        for y in (native_min[1], native_max[1])
        for z in (native_min[2], native_max[2])
    ]
    source_mesh.faces = [(0, 1, 3), (0, 3, 2), (4, 5, 7)]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    for name, position in {
        "pelvis_g": (0.0, 0.0, 1.4),
        "tail_g": (0.0, -4.0, 1.5),
        "head_g": (0.0, 1.5, 2.0),
    }.items():
        bone = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=reference_root)
        bone.external_world_position = position
        reference_root.children.append(bone)
    reference_mesh = ModelNode(
        name="native_bounds",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    reference_mesh.vertices = list(source_mesh.vertices)
    reference_mesh.bone_map = ["pelvis_g", "tail_g", "head_g"]
    reference_mesh.skin_data = [object()] * len(reference_mesh.vertices)
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()
    before_bounds = (source.bb_min, source.bb_max)

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )

    assert result["fit_policy"] == "native_template_kotor_space_replacement"
    assert result["scale"] == pytest.approx(1.0)
    assert result["offset"] == pytest.approx((0.0, 0.0, 0.0))
    assert source.bb_min == pytest.approx(before_bounds[0])
    assert source.bb_max == pytest.approx(before_bounds[1])
    fit_report = source.metadata["kotor_fit_report"]
    assert fit_report["confidence"] == pytest.approx(0.95)
    assert fit_report["fallback_used"] is False
    assert fit_report["fit_transform"]["translation"] == pytest.approx([0.0, 0.0, 0.0])


def test_unit_scale_same_resref_creature_replacement_uses_native_bounds() -> None:
    from src.core.characters.headless_body_workflow import _vertex_bounds, normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source.metadata = {
        "external_import": {
            "source_path": r"C:\mods\C_DrexlF_UV.obj",
            "target_axis_system": "kotor_z_up",
            "axis_conversion": "obj_native_axes",
        }
    }
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF_UV", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.457855, -0.104942, -0.5),
        (0.457855, 0.104942, 0.5),
    ]
    source_mesh.normals = [(1.0, 1.0, 0.0)]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    reference_mesh = ModelNode(
        name="native_bounds",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    native_min = (-4.37943696975708, -5.948987007141113, 0.9093970060348511)
    native_max = (4.452073097229004, 2.138275146484375, 2.763010025024414)
    reference_mesh.vertices = [
        (x, y, z)
        for x in (native_min[0], native_max[0])
        for y in (native_min[1], native_max[1])
        for z in (native_min[2], native_max[2])
    ]
    reference_mesh.bone_map = ["pelvis_g", "tail6_g", "head_g"]
    reference_mesh.skin_data = [object()] * len(reference_mesh.vertices)
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )

    assert result["fit_policy"] == "native_template_scaled_bounds_replacement"
    assert result["scale_basis"] == "native_template_axis_bounds_ratio"
    assert len(result["axis_scales"]) == 3
    assert getattr(source_mesh, "_gr_vertices_in_kotor_world", False) is True
    assert int(getattr(source_mesh, "vertex_space", 0) or 0) == 1
    fitted_min, fitted_max = _vertex_bounds(source)
    assert fitted_min == pytest.approx(native_min)
    assert fitted_max == pytest.approx(native_max)
    mesh_render_data = _load_native_python_module(
        "ghostrigger_mesh_render_data_under_test",
        r"native\GhostRigger.Core.Rendering\Python\src\core\rendering\mesh_render_data.py",
    )
    render_matrix = mesh_render_data.mesh_model_matrix_for_node(source_mesh)
    assert [
        float(value)
        for row in render_matrix.tolist()
        for value in row
    ] == pytest.approx([
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ])
    fit_report = source.metadata["kotor_fit_report"]
    assert fit_report["fit_policy"] == "native_template_scaled_bounds_replacement"
    assert fit_report["fit_transform"]["non_uniform_scale_baked"] is True
    assert fit_report["source_forward_axis"] == "-z"
    assert fit_report["source_up_axis"] == "+y"
    assert max(result["axis_scales"]) / min(result["axis_scales"]) < 1.2
    rotation_values = [
        value
        for row in fit_report["fit_transform"]["rotation_matrix"]
        for value in row
    ]
    assert rotation_values == pytest.approx([
        1.0, 0.0, 0.0,
        0.0, 0.0, -1.0,
        0.0, 1.0, 0.0,
    ])
    assert fit_report["fitted_visual_overlay"]["source"]["bounds"]["min"] == pytest.approx(native_min)
    assert fit_report["fitted_visual_overlay"]["source"]["bounds"]["max"] == pytest.approx(native_max)
    linear = fit_report["fit_transform"]["linear_matrix"]
    a, b, c = linear[0]
    d, e, f = linear[1]
    g, h, i = linear[2]
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    inverse = (
        ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det),
        ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det),
        ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det),
    )
    normal_matrix = (
        (inverse[0][0], inverse[1][0], inverse[2][0]),
        (inverse[0][1], inverse[1][1], inverse[2][1]),
        (inverse[0][2], inverse[1][2], inverse[2][2]),
    )
    expected_raw = tuple(
        sum(normal_matrix[row][col] * (1.0, 1.0, 0.0)[col] for col in range(3))
        for row in range(3)
    )
    expected_len = math.sqrt(sum(value * value for value in expected_raw))
    assert source_mesh.normals[0] == pytest.approx(tuple(value / expected_len for value in expected_raw))


def test_same_resref_creature_replacement_uses_native_cloud_to_choose_orientation() -> None:
    from src.core.characters.headless_body_workflow import _vertex_bounds, normalize_external_model_for_kotor
    from src.core.geometry.model_data import (
        BoneWeight,
        CharacterMode,
        GameVersion,
        KotorModel,
        ModelNode,
        NodeFlags,
        VertexSkinData,
    )

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source.metadata = {
        "external_import": {
            "source_path": r"C:\mods\C_DrexlF_UV.obj",
            "target_axis_system": "kotor_z_up",
            "axis_conversion": "obj_native_axes",
        }
    }
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF_UV", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.45, -0.10, -0.50),
        (0.45, -0.10, -0.48),
        (0.40, 0.10, -0.18),
        (-0.35, 0.10, -0.15),
        (-0.20, -0.08, 0.05),
        (0.30, -0.07, 0.20),
        (0.42, 0.07, 0.50),
        (-0.44, 0.09, 0.47),
    ]
    source_mesh.faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 5, 6), (4, 6, 7),
        (0, 4, 5), (0, 5, 1),
        (2, 6, 7), (2, 7, 3),
    ]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    scale = 3.0
    offset = (1.25, -2.0, 0.75)

    def native_point(point):
        # Native target x<-source z, y<-source x, z<-source y.  This is the
        # Drexl replacement orientation that bounds alone could not identify.
        return (
            point[2] * scale + offset[0],
            point[0] * scale + offset[1],
            point[1] * scale + offset[2],
        )

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    native_vertices = [native_point(point) for point in source_mesh.vertices]
    high_wing_pivot_z = max(point[2] for point in native_vertices) + 0.25
    donor_bones = {
        "pelvis_g": native_point((0.0, 0.0, 0.0)),
        "tail6_g": native_point((0.2, 0.0, 0.25)),
        "head_g": native_point((-0.25, 0.0, -0.25)),
        "wingtip_g": (0.0, -2.0, high_wing_pivot_z),
    }
    for name, position in donor_bones.items():
        bone = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=reference_root)
        bone.external_world_position = position
        reference_root.children.append(bone)
    reference_mesh = ModelNode(
        name="native_bounds",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    reference_mesh.vertices = native_vertices
    reference_mesh.faces = list(source_mesh.faces)
    reference_mesh.bone_map = list(donor_bones)
    reference_mesh.skin_data = [
        VertexSkinData([BoneWeight(index % len(reference_mesh.bone_map), 1.0)])
        for index, _vertex in enumerate(reference_mesh.vertices)
    ]
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )

    fit_report = source.metadata["kotor_fit_report"]
    # Correspondence registration is now the first creature-fit policy.  This
    # fixture is an exact rigid+uniform transform of the donor surface, so the
    # stronger policy must win instead of falling through to the legacy
    # bounds/chamfer lane.
    assert result["fit_policy"] == "correspondence_surface_registration"
    assert result["trace_version"] == "ghostrigger.fit/v2"
    assert result["scale"] == pytest.approx(scale)
    assert result["surface_confidence"] == pytest.approx(1.0)
    trace = result["correspondence_fit"]
    assert trace["trace_version"] == "ghostrigger.correspondence/v1"
    assert trace["falsifier_a"]["passed"] is True
    assert trace["falsifier_b"]["passed"] is True
    assert trace["applied_transform_direction"] == (
        "imported_to_kotor(inverse_of_donor_to_imported)"
    )
    assert fit_report["fit_policy"] == "correspondence_surface_registration"
    assert fit_report["fallback_used"] is False
    assert fit_report["source_forward_axis"] == "+z"
    assert fit_report["source_up_axis"] == "+y"
    fitted_min, fitted_max = _vertex_bounds(source)
    assert fitted_min == pytest.approx(reference.bb_min)
    assert fitted_max == pytest.approx(reference.bb_max)


def test_same_resref_anchor_padding_scales_without_retranslating() -> None:
    from src.core.characters.headless_body_workflow import (
        _axis_scale_padding_to_contain_points,
        _axis_scaled_matrix,
        _mat_vec,
        _transform_bounds,
        _vec_add,
    )

    bounds = ((-1.0, -0.5, -1.0), (1.0, 0.5, 1.0))
    rotation = (
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    axis_scales = (2.0, 2.0, 2.0)
    offset = (0.0, 0.0, 0.0)
    target_points = [(0.0, -1.06, 0.0), (0.0, 1.06, 0.0)]

    result = _axis_scale_padding_to_contain_points(
        bounds=bounds,
        rotation_matrix=rotation,
        axis_scales=axis_scales,
        offset=offset,
        target_points=target_points,
    )

    assert result is not None
    assert result["adjusted_axes"] == ["y"]
    assert result["offset"] == pytest.approx(offset)
    assert result["axis_scales"][1] > axis_scales[1]
    padded_matrix = result["linear_matrix"]

    def transform_point(point):
        return _vec_add(_mat_vec(padded_matrix, point), result["offset"])

    fitted_min, fitted_max = _transform_bounds(bounds, transform_point)
    assert fitted_min[1] <= target_points[0][1]
    assert fitted_max[1] >= target_points[1][1]


def test_creature_mode_obj_fit_uses_flat_bounds_not_humanoid_height() -> None:
    from src.core.characters.headless_body_workflow import normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF_UV", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.457855, -0.104942, -0.5),
        (0.457855, 0.104942, 0.5),
    ]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    reference_mesh = ModelNode(name="native_bounds", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=reference_root)
    reference_mesh.vertices = [
        (-4.3895, -5.8350, -1.0691),
        (4.4420, 2.1641, 1.8930),
    ]
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )

    assert result["fit_policy"] == "creature_bounds_basis"
    assert result["scale"] > 8.0
    fit_report = source.metadata["kotor_fit_report"]
    assert fit_report["source_up_axis"] == "+y"
    assert fit_report["source_forward_axis"] in {"+z", "-z"}
    assert fit_report["fallback_used"] is False
    assert source.bb_min[2] == pytest.approx(reference.bb_min[2])
    assert (source.bb_min[0] + source.bb_max[0]) * 0.5 == pytest.approx(
        (reference.bb_min[0] + reference.bb_max[0]) * 0.5
    )
    assert (source.bb_min[1] + source.bb_max[1]) * 0.5 == pytest.approx(
        (reference.bb_min[1] + reference.bb_max[1]) * 0.5
    )


def test_creature_containment_fit_uses_skin_bone_map_and_open_mesh_axis_seed() -> None:
    from src.core.characters.headless_body_workflow import _vertex_bounds, normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF_UV", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.457855, -0.104942, -0.5),
        (0.457855, -0.104942, -0.5),
        (0.457855, 0.104942, -0.5),
        (-0.457855, 0.104942, -0.5),
        (-0.457855, -0.104942, 0.5),
        (0.457855, -0.104942, 0.5),
        (0.457855, 0.104942, 0.5),
        (-0.457855, 0.104942, 0.5),
    ]
    source_mesh.faces = [(0, 1, 2), (0, 2, 3), (4, 5, 6)]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    donor_bones = {
        "pelvis_g": (0.01, -0.06, 1.45),
        "tail6_g": (0.25, -4.91, 1.71),
        "Lhand_g": (-0.84, 0.10, 1.49),
        "Rhand_g": (0.87, 0.10, 1.41),
        "head_g": (0.03, 1.72, 2.03),
    }
    for name, position in donor_bones.items():
        bone = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=reference_root)
        bone.external_world_position = position
        reference_root.children.append(bone)
    reference_mesh = ModelNode(
        name="C_DrexlF",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    reference_mesh.vertices = [
        (-4.3794, -5.9490, 0.9094),
        (4.4521, 2.1383, 2.7630),
    ]
    reference_mesh.bone_map = list(donor_bones)
    reference_mesh.skin_data = [object(), object()]
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
    )

    assert result["fit_policy"] == "containment_bone_inside_mesh"
    assert result["scale"] > 8.0
    assert result["fit_method"] == "oriented_bounds_reference_seed"
    assert result["containment_volume"] == "oriented_bounds"
    assert result["surface_containment_checked"] is False
    assert result["containment_guarantee"] == "oriented_bounds_only"
    assert result["bone_position_source"] == "skin_bone_map"
    assert result["deformation_bone_count"] == len(donor_bones)
    assert result["mesh_watertight"] is False
    assert result["outside_count"] == 0
    fit_report = source.metadata["kotor_fit_report"]
    assert fit_report["fit_policy"] == "containment_bone_inside_mesh"
    assert fit_report["scale_basis"] == "oriented_bounds_reference_seed"
    assert fit_report["fit_transform"] == result["fit_transform"]
    assert fit_report["containment_fit"]["bone_position_source"] == "skin_bone_map"
    assert fit_report["containment_fit"]["surface_containment_checked"] is False
    assert fit_report["containment_fit"]["containment_guarantee"] == "oriented_bounds_only"
    rotation_values = [
        value
        for row in result["fit_transform"]["rotation_matrix"]
        for value in row
    ]
    assert rotation_values == pytest.approx([
        1.0, 0.0, 0.0,
        0.0, 0.0, -1.0,
        0.0, 1.0, 0.0,
    ])
    fitted_bounds = _vertex_bounds(source)
    assert fitted_bounds is not None
    assert fitted_bounds[0][2] == pytest.approx(reference.bb_min[2])


def test_creature_containment_fit_marks_watertight_surface_volume() -> None:
    from src.core.characters.headless_body_workflow import normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="closed_creature_shell", game_version=GameVersion.K2)
    source_root = ModelNode(name="closed_creature_shell", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="closed_shell", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.5, -0.5, -0.5),
        (0.5, -0.5, -0.5),
        (0.5, 0.5, -0.5),
        (-0.5, 0.5, -0.5),
        (-0.5, -0.5, 0.5),
        (0.5, -0.5, 0.5),
        (0.5, 0.5, 0.5),
        (-0.5, 0.5, 0.5),
    ]
    source_mesh.faces = [
        (0, 1, 2), (0, 2, 3),
        (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1),
        (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3),
        (3, 7, 4), (3, 4, 0),
    ]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_closed", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_closed", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    donor_bones = {
        "pelvis_g": (0.0, 0.0, 0.0),
        "head_g": (0.0, 0.0, 0.7),
        "Lhand_g": (-0.72, 0.08, 0.05),
        "Rhand_g": (0.76, -0.07, -0.04),
    }
    for name, position in donor_bones.items():
        bone = ModelNode(name=name, flags=int(NodeFlags.HEADER), parent=reference_root)
        bone.external_world_position = position
        reference_root.children.append(bone)
    reference_mesh = ModelNode(
        name="closed_reference_skin",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=reference_root,
    )
    reference_mesh.vertices = list(source_mesh.vertices)
    reference_mesh.bone_map = list(donor_bones)
    reference_mesh.skin_data = [object()] * len(reference_mesh.vertices)
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_closed",
        expected_mode=CharacterMode.CREATURE,
    )

    assert result["fit_policy"] == "containment_bone_inside_mesh"
    assert result["containment_volume"] == "ray_cast_surface"
    assert result["surface_containment_checked"] is True
    assert result["containment_guarantee"] == "watertight_surface_volume"
    assert result["mesh_watertight"] is True
    assert result["outside_count"] == 0


def test_creature_mode_orientation_override_bypasses_bounds_autorotation() -> None:
    from src.core.characters.headless_body_workflow import inspect_external_model_fit, normalize_external_model_for_kotor
    from src.core.geometry.model_data import CharacterMode, GameVersion, KotorModel, ModelNode, NodeFlags

    source = KotorModel(name="c_drexlf_uv", game_version=GameVersion.K2)
    source_root = ModelNode(name="c_drexlf_uv", flags=int(NodeFlags.HEADER))
    source.root_node = source_root
    source_mesh = ModelNode(name="C_DrexlF_UV", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=source_root)
    source_mesh.vertices = [
        (-0.5, -0.1, -0.45),
        (0.5, 0.1, 0.45),
    ]
    source_root.children.append(source_mesh)
    source.compute_bounds()

    reference = KotorModel(name="c_drexlf", game_version=GameVersion.K2)
    reference_root = ModelNode(name="c_drexlf", flags=int(NodeFlags.HEADER))
    reference.root_node = reference_root
    reference_mesh = ModelNode(name="native_bounds", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=reference_root)
    reference_mesh.vertices = [
        (-4.3895, -5.8350, -1.0691),
        (4.4420, 2.1641, 1.8930),
    ]
    reference_root.children.append(reference_mesh)
    reference.compute_bounds()
    override = {"source_forward_axis": "+x", "source_up_axis": "+z"}

    report = inspect_external_model_fit(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
        fit_override=override,
    )
    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
        expected_mode=CharacterMode.CREATURE,
        fit_override=override,
    )

    assert report["fit_policy"] == "manual_axis_override"
    assert report["source_forward_axis"] == "+x"
    assert report["source_up_axis"] == "+z"
    assert result["fit_policy"] == "manual_axis_override"
    assert source.metadata["kotor_fit_report"]["fit_policy"] == "manual_axis_override"


def test_source_clip_preview_model_preserves_fbx_skin_weights_for_playback() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.geometry.model_data import GameVersion
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    mesh_model = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["root"],
            "actions": [{"name": "root|Unreal Take|Base Layer"}],
            "meshes": [
                {
                    "name": "Body",
                    "is_skin": True,
                    "bone_map": ["Root", "RHand"],
                    "skin_data": [
                        [{"bone_index": 0, "weight": 1.0}],
                        [{"bone_index": 1, "weight": 0.75}, {"bone_index": 0, "weight": 0.25}],
                        [{"bone_index": 1, "weight": 1.0}],
                    ],
                    "vertices": [[-1, 0, 0], [1, 0, 0], [0, 0, 2]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0, 0], [1, 0], [0.5, 1]],
                    "faces": [[0, 1, 2]],
                    "materials": [{"name": "BodyMat", "texture": "Body_D", "diffuse": [0.5, 0.6, 0.7]}],
                }
            ],
        },
        model_name="source_body",
        game_version=GameVersion.K1,
    )

    model = build_source_clip_preview_model(_sample_clip(), mesh_model=mesh_model)
    mesh_nodes = [node for node in model.all_nodes() if getattr(node, "_gr_fbx_mesh_preview_node", False)]

    assert len(mesh_nodes) == 1
    assert mesh_nodes[0].is_skin is True
    assert getattr(mesh_nodes[0], "_gr_fbx_mesh_preview_skinned") is True
    assert mesh_nodes[0].bone_map == ["Root", "RHand"]
    assert len(mesh_nodes[0].skin_data) == len(mesh_nodes[0].vertices)
    assert mesh_nodes[0].skin_data[1].influences[0].bone_index == 1
    assert mesh_nodes[0].skin_data[1].influences[0].weight == pytest.approx(0.75)


def test_renderer_caches_numpy_skin_arrays_for_large_imported_preview_meshes() -> None:
    from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.geometry.model_data import GameVersion
    from src.core.rendering.frame_core.renderer import FrameRenderer
    from src.gui.qt_lib.windows.qt_source_clip_preview_model import build_source_clip_preview_model

    mesh_model = model_from_blender_fbx_mesh_payload(
        {
            "success": True,
            "armatures": ["root"],
            "actions": [{"name": "root|Unreal Take|Base Layer"}],
            "meshes": [
                {
                    "name": "Body",
                    "is_skin": True,
                    "bone_map": ["Root", "RHand"],
                    "skin_data": [
                        [{"bone_index": 0, "weight": 1.0}],
                        [{"bone_index": 1, "weight": 0.75}, {"bone_index": 0, "weight": 0.25}],
                        [{"bone_index": 1, "weight": 1.0}],
                    ],
                    "vertices": [[-1, 0, 0], [1, 0, 0], [0, 0, 2]],
                    "normals": [[0, 1, 0], [0, 1, 0], [0, 1, 0]],
                    "uvs": [[0, 0], [1, 0], [0.5, 1]],
                    "faces": [[0, 1, 2]],
                    "materials": [{"name": "BodyMat", "texture": "Body_D", "diffuse": [0.5, 0.6, 0.7]}],
                }
            ],
        },
        model_name="source_body",
        game_version=GameVersion.K1,
    )
    model = build_source_clip_preview_model(_sample_clip(), mesh_model=mesh_model)
    mesh_node = next(node for node in model.all_nodes() if getattr(node, "_gr_fbx_mesh_preview_node", False))
    renderer = FrameRenderer(ArcBallCamera())

    first = renderer._skin_numpy_arrays_for_node(mesh_node)
    second = renderer._skin_numpy_arrays_for_node(mesh_node)

    assert first is second
    vertices_h, bone_indices, weights = first
    assert vertices_h.shape == (3, 4)
    assert bone_indices.tolist() == [[0, -1, -1, -1], [1, 0, -1, -1], [1, -1, -1, -1]]
    assert weights[1, 0] == pytest.approx(0.75)
    assert weights[1, 1] == pytest.approx(0.25)


def test_retarget_window_source_clip_preview_populates_animation_list() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_clip_preview(_sample_clip())

        assert window.panel.anim_list.count() == 1
        assert window.panel.selected_animation() == "root|Unreal Take|Base Layer"
        assert window.panel.anim_list.currentItem().data(QtCore.Qt.UserRole) is not None
        assert window.source_viewport.model is not None
        assert getattr(window.source_viewport.model, "_gr_source_clip_preview") is True
        assert window.source_viewport._renderer._anim_pose is None
    finally:
        window.close()


def test_retarget_viewport_skips_mesh_hover_hit_tests_during_animation_playback() -> None:
    _qapp()
    from src.gui.qt_lib.viewports.qt_viewport import QtRetargetViewportWidget

    viewport = QtRetargetViewportWidget()
    try:
        viewport.model = SimpleNamespace()
        viewport._renderer._anim_pose = object()
        viewport._hovered_mesh_node = object()
        viewport._hovered_mesh_face_bounds = ((0.0, 0.0, 0.0), (1.0, 1.0, 1.0))
        viewport._mesh_hit_test_detail = lambda *_args, **_kwargs: pytest.fail("hover hit test should be suspended during retarget playback")

        viewport._update_mesh_hover(object())

        assert viewport._hovered_mesh_node is None
        assert viewport._hovered_mesh_face_bounds is None
    finally:
        viewport.close()


def test_retarget_window_source_animation_playback_uses_compact_preview_positions() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    clip = _sample_clip(
        child_local_position=(100.0, 0.0, 0.0),
        child_global_position=(0.0, 1.0, 0.0),
        root_rotation=(0.0, 0.0, 0.70710678, 0.70710678),
    )
    window = QtAnimationRetargetWindow()
    try:
        previewed: list[str] = []
        window.previewRequested.connect(previewed.append)
        window.set_source_clip_preview(clip)

        item = window.panel.anim_list.currentItem()
        assert item is not None
        window.panel.anim_list.itemDoubleClicked.emit(item)

        pose = window.source_viewport._renderer._anim_pose
        assert pose is not None
        assert pose.nodes["rhand"].position == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)
        assert pose.nodes["root"].rotation == pytest.approx((0.0, 0.0, 0.70710678, 0.70710678))
        assert previewed == []

        window.panel._preview()
        assert previewed == ["root|Unreal Take|Base Layer"]
    finally:
        window.close()


def test_retarget_window_stop_clears_source_clip_playback() -> None:
    _qapp()
    from src.gui.qt_lib.windows.qt_retarget_window import QtAnimationRetargetWindow

    window = QtAnimationRetargetWindow()
    try:
        window.set_source_clip_preview(_sample_clip())
        window.play_source_clip_animation(window.panel.selected_animation())
        assert window.source_viewport._renderer._anim_pose is not None

        window._stop_requested()

        assert window._source_clip_play_timer.isActive() is False
        assert window.source_viewport._renderer._anim_pose is None
    finally:
        window.close()


def test_mesh_converter_has_blender_fbx_mesh_fallback() -> None:
    from src.converters.mesh_converter import FBXImporter

    source = inspect.getsource(FBXImporter.import_file)

    assert "import_fbx_mesh_with_blender" in source
    assert source.index("import_fbx_mesh_with_blender") > source.index("_load_trimesh")
