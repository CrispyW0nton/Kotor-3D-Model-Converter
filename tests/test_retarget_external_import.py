"""Regression tests for Retarget Workbench external-file import routing."""

from __future__ import annotations

import inspect
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore, QtWidgets


def _qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


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
    from src.core.geometry.model_data import GameVersion, KotorModel, ModelNode, NodeFlags

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
    source_mesh.vertices = [
        (-4.3794, -5.9490, 0.9094),
        (4.4521, 2.1383, 2.7630),
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
    before_bounds = (source.bb_min, source.bb_max)

    result = normalize_external_model_for_kotor(
        source,
        game_version="K2",
        reference_model=reference,
        reference_label="c_drexlf",
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
