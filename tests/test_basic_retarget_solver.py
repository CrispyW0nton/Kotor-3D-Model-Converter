"""Synthetic gates for the first basic UE-source to Aurora retarget solver."""

from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from src.core.animation.animation_engine import SuperModelResolver, evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.fbx_importer import classify_source_node_name
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.retarget_solver import (
    RetargetSolveError,
    RetargetSolverOptions,
    retarget_source_clip_to_aurora_animation,
)
from src.core.retargeting.source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
    matrix_to_quat_xyzw,
    normalize_quat_xyzw,
)
from src.core.validation.animation_block_validator import validate_animation_block_against_model


def _quat_axis(axis: str, degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    s = math.sin(radians / 2.0)
    c = math.cos(radians / 2.0)
    if axis.upper() == "X":
        return (s, 0.0, 0.0, c)
    if axis.upper() == "Y":
        return (0.0, s, 0.0, c)
    if axis.upper() == "Z":
        return (0.0, 0.0, s, c)
    raise ValueError(axis)


def _quat_neg(quat: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return tuple(-value for value in quat)  # type: ignore[return-value]


def _quat_dot(a, b) -> float:
    qa = normalize_quat_xyzw(a)
    qb = normalize_quat_xyzw(b)
    return sum(x * y for x, y in zip(qa, qb))


def _assert_quat_equivalent(actual, expected, *, tolerance: float = 1e-5) -> None:
    assert abs(_quat_dot(actual, expected)) == pytest.approx(1.0, abs=tolerance)


def _source_clip(
    node_defs: list[tuple[str, str | None]],
    pose_globals: list[dict[str, Transform]],
    *,
    duration: float | None = None,
) -> SourceSkeletonClip:
    parents = {name: parent for name, parent in node_defs}

    def local_transforms(globals_by_name: dict[str, Transform]) -> dict[str, Transform]:
        result: dict[str, Transform] = {}
        global_matrices = {name: transform.to_matrix() for name, transform in globals_by_name.items()}
        for name, parent in node_defs:
            if parent:
                local_matrix = np.linalg.inv(global_matrices[parent]) @ global_matrices[name]
            else:
                local_matrix = global_matrices[name]
            result[name] = Transform.from_matrix(local_matrix)
        return result

    sample_count = len(pose_globals)
    clip_duration = float(duration if duration is not None else max(0, sample_count - 1))
    times = [0.0] if sample_count == 1 else [clip_duration * index / (sample_count - 1) for index in range(sample_count)]
    poses = [
        SourcePose(
            time_seconds=time_value,
            global_transforms=globals_by_name,
            local_transforms=local_transforms(globals_by_name),
        )
        for time_value, globals_by_name in zip(times, pose_globals)
    ]
    rest_pose = poses[0]
    nodes = [
        SourceSkeletonNode(
            name=name,
            parent_name=parent,
            index=index,
            rest_local=rest_pose.local_transforms[name],
            rest_global=rest_pose.global_transforms[name],
            classification=classify_source_node_name(name),
        )
        for index, (name, parent) in enumerate(node_defs)
    ]
    return SourceSkeletonClip(
        source_path="fake.fbx",
        clip_name="UE_Test",
        duration_seconds=clip_duration,
        sample_rate=30.0,
        nodes=nodes,
        rest_pose=rest_pose,
        sampled_poses=poses,
        axis_system="TEST_SOURCE_AXIS",
        unit_scale_to_meters=1.0,
    )


def _target_model(
    entries: list[
        tuple[
            str,
            str | None,
            tuple[float, float, float],
            tuple[float, float, float, float] | None,
        ]
    ],
    *,
    anim_names: tuple[str, ...] = ("pause1",),
) -> KotorModel:
    nodes = {
        name: ModelNode(name=name, position=position, rotation=rotation or (0.0, 0.0, 0.0, 1.0))
        for name, _parent, position, rotation in entries
    }
    for name, parent, _position, _rotation in entries:
        if parent:
            nodes[name].parent = nodes[parent]
            nodes[parent].children.append(nodes[name])
    return KotorModel(
        name="target",
        root_node=nodes[entries[0][0]],
        animations=[Animation(name=name, length=1.0) for name in anim_names],
    )


def _profile(mappings: list[RetargetMappingEntry], *, slot: str = "pause1") -> RetargetProfile:
    return RetargetProfile(
        name="basic_solver_profile",
        animation_slot=slot,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=mappings,
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_no_source_motion_reproduces_target_reference_pose() -> None:
    source = _source_clip(
        [("root", None), ("child", "root")],
        [
            {
                "root": Transform(),
                "child": Transform(position=(1.0, 0.0, 0.0)),
            }
        ],
        duration=0.0,
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("child", "root", (1.0, 0.0, 0.0), _quat_axis("X", 30.0)),
        ]
    )
    profile = _profile([RetargetMappingEntry("hand", "child", "child")])

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=profile,
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 0.0)

    _assert_quat_equivalent(pose.local_transforms_by_node["child"].rotation, _quat_axis("X", 30.0))
    _assert_quat_equivalent(pose.world_transforms_by_node["child"].rotation, _quat_axis("X", 30.0))


def test_root_rotation_drives_child_by_aurora_fk() -> None:
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform()},
            {"root": Transform(rotation=_quat_axis("Z", 90.0))},
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("child", "root", (1.0, 0.0, 0.0), None),
        ]
    )
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    _assert_quat_equivalent(pose.local_transforms_by_node["root"].rotation, _quat_axis("Z", 90.0))
    assert pose.world_transforms_by_node["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


def test_parent_child_mapped_motion_does_not_double_count_parent_rotation() -> None:
    root_90 = Transform(rotation=_quat_axis("Z", 90.0))
    source = _source_clip(
        [("root", None), ("child", "root")],
        [
            {
                "root": Transform(),
                "child": Transform(position=(1.0, 0.0, 0.0)),
            },
            {
                "root": root_90,
                "child": Transform(position=(0.0, 1.0, 0.0), rotation=_quat_axis("Z", 90.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("child", "root", (1.0, 0.0, 0.0), None),
        ]
    )
    profile = _profile(
        [
            RetargetMappingEntry("root", "root", "root"),
            RetargetMappingEntry("hand", "child", "child"),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    _assert_quat_equivalent(pose.local_transforms_by_node["child"].rotation, (0.0, 0.0, 0.0, 1.0))
    _assert_quat_equivalent(pose.world_transforms_by_node["child"].rotation, _quat_axis("Z", 90.0))


def test_child_local_articulation_transfers_correctly() -> None:
    root_rot = _quat_axis("Z", 90.0)
    child_local_rot = _quat_axis("X", 30.0)
    child_global = Transform.from_matrix(
        Transform(rotation=root_rot).to_matrix()
        @ Transform(position=(1.0, 0.0, 0.0), rotation=child_local_rot).to_matrix()
    )
    source = _source_clip(
        [("root", None), ("child", "root")],
        [
            {
                "root": Transform(),
                "child": Transform(position=(1.0, 0.0, 0.0)),
            },
            {
                "root": Transform(rotation=root_rot),
                "child": child_global,
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("child", "root", (1.0, 0.0, 0.0), None),
        ]
    )
    profile = _profile(
        [
            RetargetMappingEntry("root", "root", "root"),
            RetargetMappingEntry("hand", "child", "child"),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    _assert_quat_equivalent(pose.local_transforms_by_node["child"].rotation, child_local_rot)


def test_segment_direction_mode_aligns_mapped_limb_segment_when_explicitly_enabled() -> None:
    source = _source_clip(
        [("upperarm_l", None), ("lowerarm_l", "upperarm_l")],
        [
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(1.0, 0.0, 0.0)),
            },
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(0.0, 1.0, 0.0), rotation=_quat_axis("Z", 90.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "root", (0.0, 0.0, 0.0), None),
            ("lbicepl_g", "lbicep_g", (1.0, 0.0, 0.0), None),
        ]
    )
    profile = _profile(
        [
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "lbicepl_g", side="left"),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=profile,
        options=RetargetSolverOptions(rotation_transfer_mode="segment_direction"),
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    assert pose.world_transforms_by_node["lbicepl_g"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert result.report.max_segment_direction_error_degrees == pytest.approx(0.0, abs=1e-5)
    assert result.report.segment_pose_errors


def test_exact_segment_correction_keys_full_target_hierarchy() -> None:
    source = _source_clip(
        [
            ("upperarm_l", None),
            ("lowerarm_l", "upperarm_l"),
            ("hand_l", "lowerarm_l"),
            ("middle_01_l", "hand_l"),
            ("middle_03_l", "middle_01_l"),
        ],
        [
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(1.0, 0.0, 0.0)),
                "hand_l": Transform(position=(2.0, 0.0, 0.0)),
                "middle_01_l": Transform(position=(2.5, 0.0, 0.0)),
                "middle_03_l": Transform(position=(3.0, 0.0, 0.0)),
            },
            {
                "upperarm_l": Transform(),
                "lowerarm_l": Transform(position=(0.0, 1.0, 0.0), rotation=_quat_axis("Z", 90.0)),
                "hand_l": Transform(position=(0.0, 2.0, 0.0), rotation=_quat_axis("Z", 90.0)),
                "middle_01_l": Transform(position=(0.0, 2.5, 0.0), rotation=_quat_axis("Z", 90.0)),
                "middle_03_l": Transform(position=(0.0, 3.0, 0.0), rotation=_quat_axis("Z", 90.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lbicep_g", "root", (0.0, 0.0, 0.0), None),
            ("Lforearm_g", "lbicep_g", (1.0, 0.0, 0.0), None),
            ("Lhand_g", "Lforearm_g", (1.0, 0.0, 0.0), None),
            ("LbFngrB_g", "Lhand_g", (0.5, 0.0, 0.0), None),
            ("LbFngrT_g", "LbFngrB_g", (0.5, 0.0, 0.0), None),
            ("unmapped_helper", "root", (0.0, 0.0, 1.0), _quat_axis("X", 15.0)),
        ]
    )
    profile = _profile(
        [
            RetargetMappingEntry("upperarm", "upperarm_l", "lbicep_g", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "Lforearm_g", side="left"),
            RetargetMappingEntry("hand", "hand_l", "Lhand_g", side="left"),
            RetargetMappingEntry("middle_base", "middle_01_l", "LbFngrB_g", side="left"),
            RetargetMappingEntry("middle_tip", "middle_03_l", "LbFngrT_g", side="left"),
        ]
    )

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=profile,
        options=RetargetSolverOptions(
            rotation_transfer_mode="exact_segment_correction",
            key_unmapped_reference_nodes=True,
        ),
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)
    keyed_nodes = {node.name for node in result.animation_block.nodes}

    assert keyed_nodes == {node.name for node in target.all_nodes()}
    assert pose.world_transforms_by_node["Lforearm_g"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)
    assert pose.world_transforms_by_node["Lhand_g"].position == pytest.approx((0.0, 2.0, 0.0), abs=1e-6)
    assert pose.world_transforms_by_node["LbFngrB_g"].position == pytest.approx((0.0, 2.5, 0.0), abs=1e-6)
    assert pose.world_transforms_by_node["unmapped_helper"].position == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)
    assert result.report.max_segment_direction_error_degrees == pytest.approx(0.0, abs=1e-5)


def test_non_root_source_translations_are_ignored() -> None:
    source = _source_clip(
        [("root", None), ("forearm_l", "root")],
        [
            {
                "root": Transform(),
                "forearm_l": Transform(position=(1.0, 2.0, 3.0)),
            },
            {
                "root": Transform(),
                "forearm_l": Transform(position=(10.0, 20.0, 30.0)),
            },
        ],
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lforearm", "root", (1.0, 2.0, 3.0), None),
        ]
    )
    profile = _profile([RetargetMappingEntry("forearm", "forearm_l", "lforearm", side="left")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)
    anim_node = result.animation_block.nodes[0]

    assert all(controller["name"] != "position" for controller in anim_node.controllers)
    assert pose.local_transforms_by_node["lforearm"].position == pytest.approx((1.0, 2.0, 3.0))


def test_root_motion_is_stripped_by_default() -> None:
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform(position=(0.0, 0.0, 0.0))},
            {"root": Transform(position=(100.0, 0.0, 0.0))},
        ],
    )
    target = _target_model([("root", None, (5.0, 6.0, 7.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)

    assert pose.local_transforms_by_node["root"].position == pytest.approx((5.0, 6.0, 7.0))
    assert result.report.stripped_root_translation is True


def test_root_motion_policy_emits_root_position_controller() -> None:
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform(position=(0.0, 0.0, 0.0))},
            {"root": Transform(position=(2.0, 3.0, 4.0))},
        ],
    )
    target = _target_model([("root", None, (5.0, 6.0, 7.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(
        source_clip=source,
        target_model=target,
        profile=profile,
        options=RetargetSolverOptions(root_translation_policy="copy_source_root"),
    )
    pose = evaluate_aurora_animation_pose(target, result.animation_block, 1.0)
    root_node = next(node for node in result.animation_block.nodes if node.name == "root")
    position_controller = next(controller for controller in root_node.controllers if controller["name"] == "position")

    # Odyssey position keys are offsets from the target node's fixed
    # rest-local position.  The evaluated pose below must still land at the
    # absolute target-local values (5, 6, 7) -> (7, 9, 11).
    assert position_controller["values"] == [[0.0, 0.0, 0.0], [2.0, 3.0, 4.0]]
    assert pose.local_transforms_by_node["root"].position == pytest.approx((7.0, 9.0, 11.0))
    assert result.report.generated_position_track_count == 1
    assert result.report.stripped_root_translation is False


def test_quaternion_hemisphere_continuity() -> None:
    q0 = _quat_axis("Z", 10.0)
    q1 = _quat_neg(_quat_axis("Z", 20.0))
    source = _source_clip(
        [("root", None)],
        [
            {"root": Transform(rotation=q0)},
            {"root": Transform(rotation=q1)},
        ],
    )
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    values = result.animation_block.nodes[0].controllers[0]["values"]

    assert _quat_dot(values[0], values[1]) >= 0.0
    for quat in values:
        assert math.sqrt(sum(value * value for value in quat)) == pytest.approx(1.0, abs=1e-6)


def test_canonical_kotor_slot_name_is_used() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)], anim_names=("pause1",))
    profile = _profile([RetargetMappingEntry("root", "root", "root")], slot="Pause1")

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)

    assert result.animation_block.name == "pause1"


def test_generated_animation_passes_structural_validator() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)
    report = validate_animation_block_against_model(target, result.animation_block, strict=True)

    assert report.success is True


def test_solver_does_not_mutate_source_profile_or_target() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), _quat_axis("Y", 15.0))])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])
    source_before = copy.deepcopy(source)
    target_snapshot = [(node.name, node.position, node.rotation) for node in target.all_nodes()]
    profile_before = copy.deepcopy(profile)

    retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)

    assert source == source_before
    assert [(node.name, node.position, node.rotation) for node in target.all_nodes()] == target_snapshot
    assert profile == profile_before


def test_helper_twist_ik_source_mapping_is_rejected() -> None:
    source = _source_clip(
        [("root", None), ("lowerarm_twist_01_l", "root")],
        [
            {
                "root": Transform(),
                "lowerarm_twist_01_l": Transform(position=(1.0, 0.0, 0.0)),
            }
        ],
        duration=0.0,
    )
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0), None),
            ("lforearm", "root", (1.0, 0.0, 0.0), None),
        ]
    )
    profile = _profile([RetargetMappingEntry("forearm", "lowerarm_twist_01_l", "lforearm", side="left")])

    with pytest.raises(RetargetSolveError, match="classified as twist/helper"):
        retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)


def test_solver_warns_when_axis_metadata_has_no_basis_conversion() -> None:
    source = _source_clip([("root", None)], [{"root": Transform()}], duration=0.0)
    target = _target_model([("root", None, (0.0, 0.0, 0.0), None)])
    profile = _profile([RetargetMappingEntry("root", "root", "root")])

    result = retarget_source_clip_to_aurora_animation(source_clip=source, target_model=target, profile=profile)

    assert any("no basis_conversion was supplied" in warning for warning in result.warnings)
