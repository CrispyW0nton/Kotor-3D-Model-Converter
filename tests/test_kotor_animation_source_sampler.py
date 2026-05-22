"""KOTOR/Aurora source animation sampler gates for Retarget Workbench modes."""

from __future__ import annotations

import math
from copy import deepcopy

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.kotor_source_animation import (
    KotorAnimationSourceError,
    KotorAnimationSourceRequest,
    sample_kotor_animation_slot_as_source_clip,
)
from src.core.retargeting.retarget_mapping import validate_retarget_profile
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import quat_dot_xyzw
from src.core.retargeting.source_skeleton_audit import audit_source_skeleton_clip


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


def _assert_quat_equivalent(actual, expected, *, tolerance: float = 1e-6) -> None:
    assert abs(quat_dot_xyzw(actual, expected)) == pytest.approx(1.0, abs=tolerance)


def _animation_node(
    name: str,
    *,
    position_values: list[list[float]] | None = None,
    orientation_values: list[list[float]] | None = None,
    times: list[float] | None = None,
) -> ModelNode:
    key_times = times or [0.0]
    controllers = []
    if position_values is not None:
        controllers.append(
            {
                "type": 8,
                "name": "position",
                "columns": 3,
                "times": key_times,
                "values": position_values,
            }
        )
    if orientation_values is not None:
        controllers.append(
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": key_times,
                "values": orientation_values,
            }
        )
    return ModelNode(name=name, controllers=controllers)


def _two_node_model(
    *,
    name: str = "pmbam",
    animations: list[Animation] | None = None,
    supermodel: str = "NULL",
    child_position: tuple[float, float, float] = (1.0, 0.0, 0.0),
    child_rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> KotorModel:
    root = ModelNode(name="root")
    child = ModelNode(name="child", position=child_position, rotation=child_rotation, parent=root)
    root.children.append(child)
    return KotorModel(name=name, supermodel=supermodel, root_node=root, animations=animations or [])


def _anim(
    *,
    name: str = "pause1",
    length: float = 1.0,
    nodes: list[ModelNode] | None = None,
) -> Animation:
    return Animation(name=name, length=length, nodes=nodes or [])


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_local_kotor_slot_samples_into_source_clip() -> None:
    model = _two_node_model(animations=[_anim(nodes=[_animation_node("root", orientation_values=[[0, 0, 0, 1]])])])

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1", sample_rate=2.0))

    assert result.source_clip.clip_name == "pause1"
    assert [node.name for node in result.source_clip.nodes] == ["root", "child"]
    assert result.source_clip.sampled_poses
    assert result.report.inherited_from_supermodel is False
    assert result.report.node_count == 2
    assert result.report.controller_node_count == 1
    assert result.source_clip.axis_system == "kotor_aurora"


def test_inherited_supermodel_slot_is_accepted() -> None:
    inherited = _anim(nodes=[_animation_node("root", orientation_values=[list(_quat_axis("Z", 90.0))])])
    super_model = _two_node_model(name="S_Test", animations=[inherited])
    SuperModelResolver.prime_cache("S_Test", super_model)
    model = _two_node_model(supermodel="S_Test")

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))

    assert result.resolved_slot.slot_name == "pause1"
    assert result.report.inherited_from_supermodel is True
    assert result.source_clip.sampled_poses[-1].local_transforms["root"].rotation


def test_local_slot_wins_over_inherited_slot() -> None:
    local = _anim(nodes=[_animation_node("root", orientation_values=[list(_quat_axis("Y", 90.0))])])
    inherited = _anim(nodes=[_animation_node("root", orientation_values=[list(_quat_axis("Z", 90.0))])])
    super_model = _two_node_model(name="S_Test", animations=[inherited])
    SuperModelResolver.prime_cache("S_Test", super_model)
    model = _two_node_model(animations=[local], supermodel="S_Test")

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))

    _assert_quat_equivalent(result.source_clip.sampled_poses[-1].local_transforms["root"].rotation, _quat_axis("Y", 90.0))
    assert result.report.inherited_from_supermodel is False


def test_invalid_slot_fails_before_sampling(monkeypatch: pytest.MonkeyPatch) -> None:
    model = _two_node_model(animations=[_anim(name="pause1")])
    monkeypatch.setattr(
        "src.core.retargeting.kotor_source_animation.evaluate_aurora_animation_pose",
        lambda *_args, **_kwargs: pytest.fail("invalid slots must fail before evaluator sampling"),
    )

    with pytest.raises(KotorAnimationSourceError, match="Invalid KOTOR source animation slot"):
        sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "UE_Run_Fwd"))


def test_evaluator_fk_semantics_are_preserved() -> None:
    animation = _anim(
        nodes=[
            _animation_node(
                "root",
                orientation_values=[[0.0, 0.0, 0.0, 1.0], list(_quat_axis("Z", 90.0))],
                times=[0.0, 1.0],
            )
        ]
    )
    model = _two_node_model(animations=[animation])

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1", sample_rate=1.0))
    end_pose = result.source_clip.sampled_poses[-1]

    assert end_pose.local_transforms["child"].position == pytest.approx((1.0, 0.0, 0.0))
    assert end_pose.global_transforms["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


def test_absolute_local_controller_values_are_sampled_not_deltas() -> None:
    animation = _anim(nodes=[_animation_node("child", orientation_values=[[0.0, 0.0, 0.0, 1.0]])])
    model = _two_node_model(animations=[animation], child_rotation=_quat_axis("X", 30.0))

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))

    _assert_quat_equivalent(
        result.source_clip.sampled_poses[0].local_transforms["child"].rotation,
        (0.0, 0.0, 0.0, 1.0),
    )


def test_zero_duration_animation_samples_once() -> None:
    model = _two_node_model(animations=[_anim(length=0.0)])

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))

    assert [pose.time_seconds for pose in result.source_clip.sampled_poses] == [0.0]
    assert result.report.sample_count == 1
    assert any("zero duration" in warning for warning in result.report.warnings)


def test_quaternion_hemisphere_continuity() -> None:
    animation = _anim(
        nodes=[
            _animation_node(
                "root",
                orientation_values=[list(_quat_axis("Z", 10.0)), list(_quat_neg(_quat_axis("Z", 20.0)))],
                times=[0.0, 1.0],
            )
        ]
    )
    model = _two_node_model(animations=[animation])

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1", sample_rate=1.0))
    q0 = result.source_clip.sampled_poses[0].local_transforms["root"].rotation
    q1 = result.source_clip.sampled_poses[1].local_transforms["root"].rotation

    assert quat_dot_xyzw(q0, q1) >= 0.0
    assert math.sqrt(sum(value * value for value in q1)) == pytest.approx(1.0, abs=1e-6)


def test_sampler_does_not_mutate_source_model_or_supermodel_chain() -> None:
    animation = _anim(nodes=[_animation_node("root", orientation_values=[list(_quat_axis("Z", 45.0))])])
    model = _two_node_model(animations=[animation], supermodel="S_Test")
    super_model = _two_node_model(name="S_Test", animations=[_anim(name="walk")])
    SuperModelResolver.prime_cache("S_Test", super_model)
    before_model = deepcopy(model)
    before_super = deepcopy(super_model)

    sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))

    assert [node.name for node in model.all_nodes()] == [node.name for node in before_model.all_nodes()]
    assert [anim.name for anim in model.animations] == [anim.name for anim in before_model.animations]
    assert [node.position for node in model.all_nodes()] == [node.position for node in before_model.all_nodes()]
    assert [anim.name for anim in super_model.animations] == [anim.name for anim in before_super.animations]


def test_sampled_kotor_clip_is_compatible_with_source_audit() -> None:
    model = _two_node_model(animations=[_anim(nodes=[_animation_node("root", orientation_values=[[0, 0, 0, 1]])])])

    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))
    audit = audit_source_skeleton_clip(result.source_clip)

    assert audit.success is True
    assert result.source_clip.axis_system == "kotor_aurora"


def test_sampled_kotor_clip_can_feed_profile_validation() -> None:
    source = _two_node_model(animations=[_anim(nodes=[_animation_node("root", orientation_values=[[0, 0, 0, 1]])])])
    target = _two_node_model(name="target")
    result = sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(source, "pause1"))
    profile = RetargetProfile(
        version=1,
        name="kotor_to_kotor",
        mappings=[
            RetargetMappingEntry(role="root", source_node="root", target_node="root"),
            RetargetMappingEntry(role="hand", source_node="child", target_node="child"),
        ],
    )

    report = validate_retarget_profile(profile, result.source_clip, target)

    assert report.success is True


def test_controller_targeting_missing_source_node_is_reported() -> None:
    model = _two_node_model(animations=[_anim(nodes=[_animation_node("missing_node", orientation_values=[[0, 0, 0, 1]])])])

    with pytest.raises(KotorAnimationSourceError, match="missing_node"):
        sample_kotor_animation_slot_as_source_clip(KotorAnimationSourceRequest(model, "pause1"))
