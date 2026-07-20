"""Small foreign-rig integration fixture independent of Blender and game data."""

from __future__ import annotations

import copy

import pytest

from src.converters.blender_fbx_mesh_importer import model_from_blender_fbx_mesh_payload
from src.core.characters.custom_rigged_character_import_service import (
    CustomRiggedCharacterImportResult,
    build_self_contained_odyssey_model,
    detect_runtime_height_offset,
    imported_skeleton_from_model,
)
from src.core.characters.custom_rigged_character_build_service import CustomRiggedCharacterBuildService
from src.core.game.kotor_loader import load_model_from_bytes
from src.core.geometry.model_data import GameVersion
from src.core.mdl.mdl_writer import MDLBinaryWriter
from src.core.project.custom_rigged_character_project import AnimationMapping, CustomRiggedCharacterProject
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode
from src.core.validation.custom_rigged_character_validator import CustomRiggedCharacterSnapshot


def _matrix(*, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> list[list[float]]:
    return [
        [1.0, 0.0, 0.0, x],
        [0.0, 1.0, 0.0, y],
        [0.0, 0.0, 1.0, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _foreign_fbx_payload() -> dict:
    bones = [
        {
            "name": "foreign_root",
            "parent": None,
            "matrix_world": _matrix(),
            "head_world_position": [0.0, 0.0, 0.0],
            "tail_world_position": [0.0, 0.0, 1.0],
            "use_deform": True,
        },
        {
            "name": "odd_leg_joint",
            "parent": "foreign_root",
            "matrix_world": _matrix(z=1.0),
            "head_world_position": [0.0, 0.0, 1.0],
            "tail_world_position": [0.0, 0.0, 2.0],
            "use_deform": True,
        },
    ]
    return {
        "success": True,
        "armatures": ["CreatureRig"],
        "armature_objects": [{"name": "CreatureRig", "matrix_world": _matrix(), "bones": bones}],
        "armature_bones": bones,
        "actions": [],
        "meshes": [
            {
                "name": "foreign_skin",
                "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                "normals": [[0.0, 0.0, 1.0], [0.0, 0.0, 1.0], [0.0, 0.0, 1.0]],
                "uvs": [[0.0, 0.25], [1.0, 0.5], [0.0, 0.75]],
                "faces": [[0, 1, 2]],
                "materials": [{"name": "creature_tex", "texture": "creature_tex.png"}],
                "is_skin": True,
                "bone_map": ["foreign_root", "odd_leg_joint"],
                "skin_data": [
                    [{"bone_index": 0, "weight": 1.0}],
                    [{"bone_index": 0, "weight": 0.4}, {"bone_index": 1, "weight": 0.6}],
                    [{"bone_index": 1, "weight": 1.0}],
                ],
            }
        ],
    }


def test_foreign_hierarchy_builds_and_reloads_without_humanoid_supermodel() -> None:
    mesh_model = model_from_blender_fbx_mesh_payload(
        _foreign_fbx_payload(), model_name="foreign_source", game_version=GameVersion.K2
    )
    skeleton = imported_skeleton_from_model(mesh_model)
    project = CustomRiggedCharacterProject(creature_name="Odd Beast", resource_name="odd_beast")
    project.selected_skeleton_root = "foreign_root"
    project.export_nodes = {node.name: True for node in skeleton.nodes}
    imported = CustomRiggedCharacterImportResult(
        source_model=mesh_model,
        skeleton=skeleton,
        snapshot=CustomRiggedCharacterSnapshot(),
    )

    model, split_report = build_self_contained_odyssey_model(project, imported)

    assert model.supermodel == "NULL"
    # Odyssey's resource-named model root replaces the selected FBX authoring
    # root, matching the proven Borhek godnode -> c_borhek contract.
    assert model.root_node.name == "odd_beast"
    assert model.find_node("foreign_root") is None
    assert model.find_node("odd_leg_joint") is not None
    assert model.find_node("odd_leg_joint").parent.name == "cutscenedummy"
    assert model.find_node("pelvis_g") is None
    assert split_report[0]["parts"][0]["palette"] == 2
    skin = next(node for node in model.all_nodes() if node.is_skin)
    assert skin.bone_map == ["odd_beast", "odd_leg_joint"]
    assert len(skin.qbone_list) == len(skin.tbone_list) == 2
    assert skin.uv_v_flip is False

    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, game_version=GameVersion.K2)

    assert reloaded is not None
    assert reloaded.supermodel == "NULL"
    assert reloaded.root_node.name == "odd_beast"
    assert reloaded.find_node("foreign_root") is None
    reloaded_skin = next(node for node in reloaded.all_nodes() if node.is_skin)
    assert reloaded_skin.bone_map == ["odd_beast", "odd_leg_joint"]
    assert len(reloaded_skin.vertices) == 3
    assert reloaded_skin.uvs == [(0.0, 0.75), (1.0, 0.5), (0.0, 0.25)]


def test_flattened_fbx_loops_restore_source_vertex_indexing_for_odyssey_skin() -> None:
    payload = copy.deepcopy(_foreign_fbx_payload())
    mesh = payload["meshes"][0]
    mesh["vertices"] = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [-1.0, 0.0, 0.0],
    ]
    mesh["normals"] = [[0.0, 0.0, 1.0] for _ in mesh["vertices"]]
    mesh["uvs"] = [
        [0.0, 0.0], [1.0, 0.0], [0.0, 1.0],
        [0.0, 0.0], [0.0, 1.0], [1.0, 1.0],
    ]
    mesh["faces"] = [[0, 1, 2], [3, 4, 5]]
    mesh["source_vertex_indices"] = [0, 1, 2, 0, 2, 3]
    mesh["skin_data"] = [
        [{"bone_index": 0, "weight": 1.0}],
        [{"bone_index": 0, "weight": 1.0}],
        [{"bone_index": 1, "weight": 1.0}],
        [{"bone_index": 0, "weight": 1.0}],
        [{"bone_index": 1, "weight": 1.0}],
        [{"bone_index": 1, "weight": 1.0}],
    ]
    mesh_model = model_from_blender_fbx_mesh_payload(
        payload, model_name="indexed_source", game_version=GameVersion.K2
    )
    skeleton = imported_skeleton_from_model(mesh_model)
    project = CustomRiggedCharacterProject(creature_name="Odd Beast", resource_name="odd_beast")
    project.selected_skeleton_root = "foreign_root"
    project.export_nodes = {node.name: True for node in skeleton.nodes}
    imported = CustomRiggedCharacterImportResult(
        source_model=mesh_model,
        skeleton=skeleton,
        snapshot=CustomRiggedCharacterSnapshot(),
    )

    model, split_report = build_self_contained_odyssey_model(project, imported)
    skin = next(node for node in model.all_nodes() if node.is_skin)

    assert split_report[0]["source_vertices"] == 4
    assert len(skin.vertices) == 4
    assert skin.faces == [(0, 1, 2), (0, 2, 3)]
    assert len(skin.skin_data) == 4


def test_multiple_armatures_require_an_explicit_single_hierarchy_selection() -> None:
    payload = copy.deepcopy(_foreign_fbx_payload())
    second_bones = [{
        "name": "second_root",
        "parent": None,
        "matrix_world": _matrix(x=4.0),
        "head_world_position": [4.0, 0.0, 0.0],
        "tail_world_position": [4.0, 0.0, 1.0],
        "use_deform": True,
    }]
    payload["armatures"].append("SecondRig")
    payload["armature_objects"].append({
        "name": "SecondRig", "matrix_world": _matrix(), "bones": second_bones
    })
    model = model_from_blender_fbx_mesh_payload(
        payload, model_name="two_rigs", game_version=GameVersion.K2
    )

    unresolved = imported_skeleton_from_model(model)
    selected = imported_skeleton_from_model(model, selected_root="SecondRig :: second_root")

    assert unresolved.selection_required is True
    assert unresolved.available_root_choices == [
        "CreatureRig :: foreign_root", "SecondRig :: second_root"
    ]
    assert selected.selection_required is False
    assert selected.armature_name == "SecondRig"
    assert selected.root_names == ["second_root"]
    assert [node.name for node in selected.nodes] == ["second_root"]


def test_root_joint_height_is_mirrored_on_kotor_heightdummy() -> None:
    payload = copy.deepcopy(_foreign_fbx_payload())
    bones = payload["armature_objects"][0]["bones"]
    bones.insert(1, {
        "name": "root_joint",
        "parent": "foreign_root",
        # Blender +Y becomes KOTOR -Z in this fixture's conversion basis.
        "matrix_world": _matrix(y=-1.9724489450454712),
        "head_world_position": [0.0, -1.9724489450454712, 0.0],
        "tail_world_position": [0.0, -2.5, 0.0],
        "use_deform": True,
    })
    mesh_model = model_from_blender_fbx_mesh_payload(
        payload, model_name="runtime_height_source", game_version=GameVersion.K2
    )
    skeleton = imported_skeleton_from_model(mesh_model)
    detected, source = detect_runtime_height_offset(skeleton)
    project = CustomRiggedCharacterProject(creature_name="Odd Beast", resource_name="odd_beast")
    project.selected_skeleton_root = "foreign_root"
    project.export_nodes = {node.name: True for node in skeleton.nodes}
    project.runtime_height_offset = detected
    project.runtime_height_source = source
    project.ground_offset = 0.06
    imported = CustomRiggedCharacterImportResult(
        source_model=mesh_model,
        skeleton=skeleton,
        snapshot=CustomRiggedCharacterSnapshot(),
    )

    model, _split_report = build_self_contained_odyssey_model(project, imported)
    height = model.find_node("heightdummy")

    assert source == "root_joint"
    assert detected == 1.9724489450454712
    assert height is not None
    assert height.position[2] == pytest.approx(2.0324489450454714)


def test_animations_inherit_root_height_without_doubling_the_base_offset() -> None:
    payload = copy.deepcopy(_foreign_fbx_payload())
    bones = payload["armature_objects"][0]["bones"]
    bones.insert(1, {
        "name": "root_joint",
        "parent": "foreign_root",
        "matrix_world": _matrix(y=-1.9724489450454712),
        "head_world_position": [0.0, -1.9724489450454712, 0.0],
        "tail_world_position": [0.0, -2.5, 0.0],
        "use_deform": True,
    })
    mesh_model = model_from_blender_fbx_mesh_payload(
        payload, model_name="runtime_height_animation_source", game_version=GameVersion.K2
    )
    skeleton = imported_skeleton_from_model(mesh_model)
    detected, source = detect_runtime_height_offset(skeleton)
    project = CustomRiggedCharacterProject(creature_name="Odd Beast", resource_name="odd_beast")
    project.selected_skeleton_root = "foreign_root"
    project.export_nodes = {node.name: True for node in skeleton.nodes}
    project.runtime_height_offset = detected
    project.runtime_height_source = source
    project.ground_offset = 0.06
    project.animation_mappings = [
        AnimationMapping(
            source_name="idle_source",
            assignment="vanilla_behavior_alias",
            exported_name="cpause1",
            confirmed=True,
            loop=True,
        )
    ]
    source_nodes = [
        SourceSkeletonNode(
            name=node.name,
            parent_name=node.parent or None,
            index=index,
            rest_local=skeleton.local_transforms[node.name],
            rest_global=skeleton.global_transforms[node.name],
        )
        for index, node in enumerate(skeleton.nodes)
    ]
    rest_pose = SourcePose(
        time_seconds=0.0,
        local_transforms=dict(skeleton.local_transforms),
        global_transforms=dict(skeleton.global_transforms),
    )
    clip = SourceSkeletonClip(
        source_path="idle_source.fbx",
        clip_name="idle_source",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=source_nodes,
        rest_pose=rest_pose,
        sampled_poses=[rest_pose],
    )
    imported = CustomRiggedCharacterImportResult(
        source_model=mesh_model,
        skeleton=skeleton,
        snapshot=CustomRiggedCharacterSnapshot(),
        clips={"idle_source": clip},
    )

    model, _split_report = build_self_contained_odyssey_model(project, imported)
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(model)
    reloaded = load_model_from_bytes(mdl_bytes, mdx_bytes, game_version=GameVersion.K2)

    assert reloaded is not None
    assert [animation.name for animation in reloaded.animations] == ["cpause1"]
    animation_names = [node.name.casefold() for node in reloaded.animations[0].nodes]
    assert animation_names[:3] == ["odd_beast", "heightdummy", "cutscenedummy"]
    assert "foreign_root" not in animation_names
    animation_root_joint = next(
        node for node in reloaded.animations[0].nodes if node.name.casefold() == "root_joint"
    )
    assert animation_root_joint.parent.name.casefold() == "cutscenedummy"
    animation_model_root = reloaded.animations[0].nodes[0]
    assert not any(
        int(controller.get("type", 0)) == 8
        for controller in animation_model_root.controllers
    )
    animation_height = next(
        node for node in reloaded.animations[0].nodes if node.name.casefold() == "heightdummy"
    )
    position_controllers = [
        controller
        for controller in animation_height.controllers
        if int(controller.get("type", 0)) == 8
    ]
    assert position_controllers == []
    roundtrip = CustomRiggedCharacterBuildService().validate_serialized_model(
        project, mdl_bytes, mdx_bytes
    )
    assert roundtrip["animation_runtime_height_verified"] == 1
    assert roundtrip["animation_runtime_height_mode"] == "inherit_base_without_delta"

    source_animation_height = next(
        node for node in model.animations[0].nodes if node.name.casefold() == "heightdummy"
    )
    source_animation_height.controllers.append({
        "type": 8,
        "name": "position",
        "columns": 3,
        "times": [0.0],
        "values": [[0.0, 0.0, 2.0324489450454714]],
    })
    bad_mdl, bad_mdx = MDLBinaryWriter().write(model)
    with pytest.raises(ValueError, match="lift the creature twice"):
        CustomRiggedCharacterBuildService().validate_serialized_model(
            project, bad_mdl, bad_mdx
        )
