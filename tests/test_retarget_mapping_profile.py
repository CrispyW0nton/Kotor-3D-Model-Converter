"""Retarget mapping profile persistence, suggestions, and validation gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.game.kotor_loader import load_model_from_file
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.fbx_importer import classify_source_node_name
from src.core.retargeting.retarget_mapping import (
    detect_side,
    suggest_mixamo_to_aurora_mapping,
    suggest_initial_mapping,
    suggest_source_roles,
    suggest_ue5_to_aurora_mapping,
    validate_retarget_profile,
)
from src.core.retargeting.retarget_profile import (
    RetargetMappingEntry,
    RetargetProfile,
    load_retarget_profile,
    save_retarget_profile,
)
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode, Transform


def _source_clip(
    names: list[str],
    *,
    parents: dict[str, str | None] | None = None,
) -> SourceSkeletonClip:
    parents = parents or {}
    globals_by_name = {
        name: Transform(position=(float(index), 0.0, 0.0))
        for index, name in enumerate(names)
    }
    locals_by_name = dict(globals_by_name)
    pose = SourcePose(time_seconds=0.0, global_transforms=globals_by_name, local_transforms=locals_by_name)
    nodes = [
        SourceSkeletonNode(
            name=name,
            parent_name=parents.get(name),
            index=index,
            rest_local=locals_by_name[name],
            rest_global=globals_by_name[name],
            classification=classify_source_node_name(name),
        )
        for index, name in enumerate(names)
    ]
    return SourceSkeletonClip(
        source_path="fake.fbx",
        clip_name="Idle",
        duration_seconds=0.0,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=pose,
        sampled_poses=[pose],
    )


def _target_model(
    names: list[str],
    *,
    parents: dict[str, str | None] | None = None,
    anims: tuple[str, ...] = (),
) -> KotorModel:
    parents = parents or {}
    nodes = {name: ModelNode(name=name, position=(float(index), 0.0, 0.0)) for index, name in enumerate(names)}
    for name, node in nodes.items():
        parent_name = parents.get(name)
        if parent_name:
            node.parent = nodes[parent_name]
            nodes[parent_name].children.append(node)
    root = nodes[names[0]]
    return KotorModel(
        name="target_model",
        root_node=root,
        animations=[Animation(name=anim, length=1.0) for anim in anims],
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_profile_json_roundtrip_preserves_fields(tmp_path: Path) -> None:
    profile = RetargetProfile(
        name="ue5_to_kotor",
        source_clip_hint="clip.fbx",
        target_model_hint="pmbam",
        animation_slot="pause1",
        source_reference={"mode": "clip_time", "time_seconds": 1.0},
        target_reference={"mode": "animation_slot_time", "slot": "pause1", "time_seconds": 0.25},
        mappings=[
            RetargetMappingEntry(
                role="forearm",
                source_node=" lowerarm_l ",
                target_node=" lforearm_g ",
                side="left",
                notes="test note",
            )
        ],
        ignored_source_nodes=["ik_foot_root"],
        twist_sources={"forearm_l": ["lowerarm_twist_01_l"]},
        metadata={"custom": {"kept": True}},
    )
    path = tmp_path / "profile.json"

    save_retarget_profile(profile, path)
    loaded = load_retarget_profile(path)

    assert loaded.name == "ue5_to_kotor"
    assert loaded.mappings[0].source_node == "lowerarm_l"
    assert loaded.mappings[0].target_node == "lforearm_g"
    assert loaded.ignored_source_nodes == ["ik_foot_root"]
    assert loaded.twist_sources == {"forearm_l": ["lowerarm_twist_01_l"]}
    assert loaded.metadata == {"custom": {"kept": True}}

    bad_path = tmp_path / "bad_profile.json"
    bad_path.write_text('{"version": 999, "name": "future"}', encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported retarget profile version"):
        load_retarget_profile(bad_path)


def test_source_role_suggestions_classify_ue_style_names() -> None:
    clip = _source_clip(
        [
            "root",
            "pelvis",
            "spine_01",
            "spine_03",
            "clavicle_l",
            "upperarm_l",
            "lowerarm_l",
            "hand_l",
            "thigh_r",
            "calf_r",
            "foot_r",
            "lowerarm_twist_01_l",
            "ik_foot_root",
        ]
    )

    suggestions = suggest_source_roles(clip)

    assert suggestions["pelvis"] == "pelvis"
    assert suggestions["spine_01"] == "spine"
    assert suggestions["spine_03"] == "chest"
    assert suggestions["upperarm_l"] == "upperarm"
    assert suggestions["lowerarm_l"] == "forearm"
    assert suggestions["hand_l"] == "hand"
    assert suggestions["thigh_r"] == "thigh"
    assert suggestions["calf_r"] == "calf"
    assert suggestions["foot_r"] == "foot"
    assert "lowerarm_twist_01_l" not in suggestions
    assert "ik_foot_root" not in suggestions
    assert detect_side("upperarm_l") == "left"
    assert detect_side("thigh_r") == "right"


def test_initial_mapping_does_not_duplicate_target_nodes() -> None:
    clip = _source_clip(["root", "spine_01", "spine_02", "spine_04"])
    target = _target_model(["root", "torso_g"], parents={"torso_g": "root"})

    profile = suggest_initial_mapping(clip, target)

    target_nodes = [entry.target_node.lower() for entry in profile.mappings]
    assert target_nodes.count("torso_g") == 1
    assert validate_retarget_profile(profile, clip, target).success is True


def test_verified_ue5_to_aurora_mapping_uses_rename_map_and_target_casing() -> None:
    clip = _source_clip(
        [
            "attach",
            "pelvis",
            "spine_01",
            "spine_03",
            "clavicle_l",
            "upperarm_l",
            "lowerarm_l",
            "hand_l",
            "middle_01_l",
            "middle_03_l",
            "thigh_l",
            "calf_l",
            "foot_l",
            "ball_l",
            "clavicle_r",
            "upperarm_r",
            "lowerarm_r",
            "hand_r",
            "middle_01_r",
            "middle_03_r",
            "thigh_r",
            "calf_r",
            "foot_r",
            "ball_r",
            "head",
            "lowerarm_twist_01_l",
        ]
    )
    target = load_model_from_file(
        "tests/fixtures/kotor_stock/k1/pmbam.mdl",
        "tests/fixtures/kotor_stock/k1/pmbam.mdx",
    )

    profile = suggest_ue5_to_aurora_mapping(clip, target)
    pairs = {entry.source_node: entry.target_node for entry in profile.mappings}

    assert profile.metadata["generated_by"] == "verified_ue5_to_aurora_mapping"
    assert pairs["lowerarm_l"] == "Lforearm_g"
    assert pairs["hand_l"] == "Lhand_g"
    assert pairs["middle_01_l"] == "LbFngrB_g"
    assert pairs["middle_03_l"] == "LbFngrT_g"
    assert pairs["lowerarm_r"] == "Rforearm_g"
    assert pairs["hand_r"] == "Rhand_g"
    assert pairs["ball_l"] == "lfootT_g"
    assert pairs["ball_r"] == "rfootT_g"
    assert "headhook" not in {entry.target_node.lower() for entry in profile.mappings}
    assert profile.metadata["recommended_rotation_transfer_mode"] == "exact_segment_correction"
    assert profile.metadata["key_unmapped_reference_nodes"] is True

    report = validate_retarget_profile(profile, clip, target)
    assert report.success is True


def test_verified_mixamo_to_aurora_mapping_uses_family_specific_policy() -> None:
    mixamo_names = [
        "mixamorig:Hips",
        "mixamorig:Spine",
        "mixamorig:Spine1",
        "mixamorig:Spine2",
        "mixamorig:Neck",
        "mixamorig:Head",
        "mixamorig:RightShoulder",
        "mixamorig:RightArm",
        "mixamorig:RightForeArm",
        "mixamorig:RightHand",
        "mixamorig:RightHandMiddle1",
        "mixamorig:RightHandMiddle3",
        "mixamorig:LeftShoulder",
        "mixamorig:LeftArm",
        "mixamorig:LeftForeArm",
        "mixamorig:LeftHand",
        "mixamorig:LeftHandMiddle1",
        "mixamorig:LeftHandMiddle3",
        "mixamorig:RightUpLeg",
        "mixamorig:RightLeg",
        "mixamorig:RightFoot",
        "mixamorig:RightToeBase",
        "mixamorig:LeftUpLeg",
        "mixamorig:LeftLeg",
        "mixamorig:LeftFoot",
        "mixamorig:LeftToeBase",
    ]
    clip = _source_clip(mixamo_names)
    target = load_model_from_file(
        "tests/fixtures/kotor_stock/k1/pmbam.mdl",
        "tests/fixtures/kotor_stock/k1/pmbam.mdx",
    )

    profile = suggest_mixamo_to_aurora_mapping(clip, target)
    pairs = {entry.source_node: entry.target_node for entry in profile.mappings}

    assert profile.metadata["generated_by"] == "verified_mixamo_to_aurora_mapping"
    assert profile.metadata["source_skeleton_family"] == "mixamo"
    assert pairs["mixamorig:RightHand"] == "Rhand_g"
    assert pairs["mixamorig:LeftHand"] == "Lhand_g"
    assert pairs["mixamorig:RightFoot"] == "rfoot_g"
    assert pairs["mixamorig:LeftFoot"] == "lfoot_g"
    assert "handconjure" not in {entry.target_node.lower() for entry in profile.mappings}
    assert "headhook" not in {entry.target_node.lower() for entry in profile.mappings}
    assert profile.metadata["recommended_rotation_transfer_mode"] == "exact_segment_correction"
    assert profile.metadata["key_unmapped_reference_nodes"] is True

    report = validate_retarget_profile(profile, clip, target)
    assert report.success is True


def test_validation_rejects_unknown_source_node() -> None:
    clip = _source_clip(["root", "pelvis"])
    target = _target_model(["root", "pelvis_g"], parents={"pelvis_g": "root"})
    profile = RetargetProfile(
        name="ue5_manny_to_kotor_humanoid",
        mappings=[RetargetMappingEntry(role="pelvis", source_node="UE_UnknownBone", target_node="pelvis_g")],
    )

    report = validate_retarget_profile(profile, clip, target)

    assert report.success is False
    assert any("UE_UnknownBone" in error and "does not contain" in error for error in report.errors)


def test_validation_rejects_unknown_target_node() -> None:
    clip = _source_clip(["root", "lowerarm_l"])
    target = _target_model(["root", "lforearm_g"], parents={"lforearm_g": "root"})
    profile = RetargetProfile(
        name="ue5_manny_to_kotor_humanoid",
        mappings=[
            RetargetMappingEntry(
                role="forearm",
                source_node="lowerarm_l",
                target_node="UE_Mannequin_lowerarm_l",
                side="left",
            )
        ],
    )

    report = validate_retarget_profile(profile, clip, target)

    assert report.success is False
    assert any(
        "KOTOR controllers must target existing Aurora nodes, not UE skeleton bones" in error
        for error in report.errors
    )


def test_validation_rejects_duplicate_target_node_for_normal_mappings() -> None:
    clip = _source_clip(["root", "upperarm_l", "lowerarm_l"])
    target = _target_model(["root", "larm_g"], parents={"larm_g": "root"})
    profile = RetargetProfile(
        name="duplicate_target",
        mappings=[
            RetargetMappingEntry(role="upperarm", source_node="upperarm_l", target_node="larm_g", side="left"),
            RetargetMappingEntry(role="forearm", source_node="lowerarm_l", target_node="larm_g", side="left"),
        ],
    )

    report = validate_retarget_profile(profile, clip, target)

    assert report.success is False
    assert any("mapped by multiple" in error for error in report.errors)


def test_twist_helper_source_cannot_be_normal_mapping_by_default() -> None:
    clip = _source_clip(["root", "lowerarm_twist_01_l"])
    target = _target_model(["root", "lforearm_g"], parents={"lforearm_g": "root"})
    profile = RetargetProfile(
        name="twist_misuse",
        mappings=[
            RetargetMappingEntry(
                role="forearm",
                source_node="lowerarm_twist_01_l",
                target_node="lforearm_g",
                side="left",
            )
        ],
    )

    report = validate_retarget_profile(profile, clip, target)

    assert report.success is False
    assert any("classified as twist/helper" in error for error in report.errors)

    allowed = RetargetProfile(
        name="twist_allowed",
        mappings=[
            RetargetMappingEntry(
                role="forearm",
                source_node="lowerarm_twist_01_l",
                target_node="lforearm_g",
                side="left",
                allow_helper_mapping=True,
            )
        ],
    )
    allowed_report = validate_retarget_profile(allowed, clip, target)
    assert allowed_report.success is True
    assert any("classified as twist/helper" in warning for warning in allowed_report.warnings)


def test_animation_slot_in_profile_is_validated() -> None:
    clip = _source_clip(["root", "pelvis"])
    target = _target_model(["root", "pelvis_g"], parents={"pelvis_g": "root"}, anims=("pause1",))
    mapping = [RetargetMappingEntry(role="pelvis", source_node="pelvis", target_node="pelvis_g")]

    valid = RetargetProfile(name="slot_valid", animation_slot="pause1", mappings=mapping)
    assert validate_retarget_profile(valid, clip, target).success is True

    invalid = RetargetProfile(name="slot_invalid", animation_slot="UE_Run_Fwd", mappings=mapping)
    report = validate_retarget_profile(invalid, clip, target)

    assert report.success is False
    assert any("UE clip names are not KOTOR animation slot names" in error for error in report.errors)
