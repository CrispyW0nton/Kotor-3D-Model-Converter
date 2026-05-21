"""Reference-pose and mapped-segment audit gates for UE-to-Aurora retargeting."""

from __future__ import annotations

import math

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.reference_pose import build_reference_pose_pair
from src.core.retargeting.retarget_frame_audit import audit_retarget_reference_frames
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import SourcePose, SourceSkeletonClip, SourceSkeletonNode, Transform


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


def _animation_node(
    name: str,
    *,
    orientation: tuple[float, float, float, float] | None = None,
    position: tuple[float, float, float] | None = None,
) -> ModelNode:
    controllers = []
    if orientation is not None:
        controllers.append(
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": [0.0],
                "values": [list(orientation)],
            }
        )
    if position is not None:
        controllers.append(
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": [0.0],
                "values": [list(position)],
            }
        )
    return ModelNode(name=name, controllers=controllers)


def _target_model(
    entries: list[tuple[str, str | None, tuple[float, float, float]]],
    *,
    animations: list[Animation] | None = None,
) -> KotorModel:
    nodes = {name: ModelNode(name=name, position=position) for name, _parent, position in entries}
    for name, parent_name, _position in entries:
        if parent_name:
            nodes[name].parent = nodes[parent_name]
            nodes[parent_name].children.append(nodes[name])
    return KotorModel(name="target_model", root_node=nodes[entries[0][0]], animations=animations or [])


def _source_clip(
    entries: list[tuple[str, str | None, tuple[float, float, float]]],
    *,
    second_pose: dict[str, tuple[float, float, float]] | None = None,
) -> SourceSkeletonClip:
    def pose_at(time_seconds: float, overrides: dict[str, tuple[float, float, float]] | None = None) -> SourcePose:
        globals_by_name = {
            name: Transform(position=(overrides or {}).get(name, position))
            for name, _parent, position in entries
        }
        locals_by_name = dict(globals_by_name)
        return SourcePose(time_seconds=time_seconds, global_transforms=globals_by_name, local_transforms=locals_by_name)

    rest_pose = pose_at(0.0)
    sampled_poses = [rest_pose]
    if second_pose is not None:
        sampled_poses.append(pose_at(1.0, second_pose))
    nodes = [
        SourceSkeletonNode(
            name=name,
            parent_name=parent_name,
            index=index,
            rest_local=rest_pose.local_transforms[name],
            rest_global=rest_pose.global_transforms[name],
            classification="root" if parent_name is None else "deform",
        )
        for index, (name, parent_name, _position) in enumerate(entries)
    ]
    return SourceSkeletonClip(
        source_path="fake.fbx",
        clip_name="Idle",
        duration_seconds=1.0 if second_pose is not None else 0.0,
        sample_rate=1.0,
        nodes=nodes,
        rest_pose=rest_pose,
        sampled_poses=sampled_poses,
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_target_rest_reference_pose_builds_local_and_global_transforms() -> None:
    source = _source_clip([("root", None, (0.0, 0.0, 0.0))])
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0)),
            ("pelvis", "root", (1.0, 0.0, 0.0)),
            ("chest", "pelvis", (0.0, 2.0, 0.0)),
        ]
    )
    profile = RetargetProfile(source_reference={"mode": "clip_rest"}, target_reference={"mode": "target_rest"})

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)

    assert pair.target_reference_mode == "target_rest"
    assert pair.target_local_transforms["chest"].position == pytest.approx((0.0, 2.0, 0.0))
    assert pair.target_global_transforms["chest"].position == pytest.approx((1.0, 2.0, 0.0))


def test_source_clip_rest_reference_is_used() -> None:
    source = _source_clip([("root", None, (3.0, 4.0, 5.0))])
    target = _target_model([("root", None, (0.0, 0.0, 0.0))])
    profile = RetargetProfile(source_reference={"mode": "clip_rest"}, target_reference={"mode": "target_rest"})

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)

    assert pair.source_pose is source.rest_pose
    assert pair.source_pose.global_transforms["root"].position == pytest.approx((3.0, 4.0, 5.0))


def test_source_clip_time_reference_selects_requested_pose() -> None:
    source = _source_clip(
        [("root", None, (0.0, 0.0, 0.0))],
        second_pose={"root": (9.0, 8.0, 7.0)},
    )
    target = _target_model([("root", None, (0.0, 0.0, 0.0))])
    profile = RetargetProfile(
        source_reference={"mode": "clip_time", "time_seconds": 1.0},
        target_reference={"mode": "target_rest"},
    )

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)

    assert pair.source_pose.time_seconds == pytest.approx(1.0)
    assert pair.source_pose.global_transforms["root"].position == pytest.approx((9.0, 8.0, 7.0))


def test_target_animation_slot_reference_uses_evaluator() -> None:
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[_animation_node("root", orientation=_quat_axis("Z", 90.0))],
    )
    source = _source_clip([("root", None, (0.0, 0.0, 0.0))])
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0)),
            ("child", "root", (1.0, 0.0, 0.0)),
        ],
        animations=[animation],
    )
    profile = RetargetProfile(
        animation_slot="pause1",
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "animation_slot_time", "slot": "pause1", "time_seconds": 0.0},
    )

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)

    assert pair.target_reference_mode == "animation_slot_time"
    assert pair.target_global_transforms["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


def test_reference_builder_does_not_mutate_target_model() -> None:
    source = _source_clip([("root", None, (0.0, 0.0, 0.0))])
    target = _target_model(
        [
            ("root", None, (0.0, 0.0, 0.0)),
            ("pelvis", "root", (1.0, 0.0, 0.0)),
        ],
        animations=[Animation(name="pause1", length=1.0)],
    )
    before = [
        (node.name, node.position, node.rotation, node.parent.name if node.parent else None)
        for node in target.all_nodes()
    ]
    before_anims = [anim.name for anim in target.animations]

    build_reference_pose_pair(
        source_clip=source,
        target_model=target,
        profile=RetargetProfile(target_reference={"mode": "target_rest"}),
    )

    after = [
        (node.name, node.position, node.rotation, node.parent.name if node.parent else None)
        for node in target.all_nodes()
    ]
    assert after == before
    assert [anim.name for anim in target.animations] == before_anims


def test_reference_frame_audit_reports_segment_lengths_and_angles() -> None:
    source = _source_clip(
        [
            ("upperarm_l", None, (0.0, 0.0, 0.0)),
            ("lowerarm_l", "upperarm_l", (1.0, 0.0, 0.0)),
        ]
    )
    target = _target_model(
        [
            ("l_bicep", None, (0.0, 0.0, 0.0)),
            ("l_forearm", "l_bicep", (0.0, 2.0, 0.0)),
        ]
    )
    profile = RetargetProfile(
        mappings=[
            RetargetMappingEntry("upperarm", "upperarm_l", "l_bicep", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "l_forearm", side="left"),
        ]
    )

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)
    audit = audit_retarget_reference_frames(profile, pair)

    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert entry.source_length == pytest.approx(1.0)
    assert entry.target_length == pytest.approx(2.0)
    assert entry.length_ratio == pytest.approx(2.0)
    assert entry.angular_difference_degrees == pytest.approx(90.0)


def test_reference_frame_audit_warns_on_zero_length_segment() -> None:
    source = _source_clip(
        [
            ("upperarm_l", None, (0.0, 0.0, 0.0)),
            ("lowerarm_l", "upperarm_l", (0.0, 0.0, 0.0)),
        ]
    )
    target = _target_model(
        [
            ("l_bicep", None, (0.0, 0.0, 0.0)),
            ("l_forearm", "l_bicep", (0.0, 2.0, 0.0)),
        ]
    )
    profile = RetargetProfile(
        mappings=[
            RetargetMappingEntry("upperarm", "upperarm_l", "l_bicep", side="left"),
            RetargetMappingEntry("forearm", "lowerarm_l", "l_forearm", side="left"),
        ]
    )

    pair = build_reference_pose_pair(source_clip=source, target_model=target, profile=profile)
    audit = audit_retarget_reference_frames(profile, pair)

    assert any("zero-length source segment" in warning for warning in audit.warnings)
