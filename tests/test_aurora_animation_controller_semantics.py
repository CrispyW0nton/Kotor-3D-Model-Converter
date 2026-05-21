"""Synthetic gates for Aurora animation controller semantics."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from src.core.animation.animation_engine import (
    SuperModelResolver,
    evaluate_aurora_animation_pose,
)
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)
from src.core.validation.animation_block_validator import (
    AnimationBlockValidationError,
    validate_animation_block_against_model,
)


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


def _quat_dot(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _assert_quat_equivalent(
    actual: tuple[float, float, float, float],
    expected: tuple[float, float, float, float],
    *,
    tolerance: float = 1e-6,
) -> None:
    # q and -q represent the same rotation, so compare absolute dot.
    assert abs(_quat_dot(actual, expected)) == pytest.approx(1.0, abs=tolerance)


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
    child_position: tuple[float, float, float] = (1.0, 0.0, 0.0),
    child_rotation: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0),
) -> KotorModel:
    root = ModelNode(name="root")
    child = ModelNode(name="child", position=child_position, rotation=child_rotation, parent=root)
    root.children.append(child)
    return KotorModel(name="synthetic", root_node=root, animations=[])


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_parent_rotation_moves_child_by_fk() -> None:
    model = _two_node_model()
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            _animation_node(
                "root",
                orientation_values=[list(_quat_axis("Z", 90.0))],
            )
        ],
    )

    pose = evaluate_aurora_animation_pose(model, animation, 0.0)

    assert pose.local_transforms_by_node["child"].position == pytest.approx((1.0, 0.0, 0.0))
    assert pose.world_transforms_by_node["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)


def test_orientation_controller_is_absolute_local_not_delta() -> None:
    model = _two_node_model(child_rotation=_quat_axis("X", 30.0))
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[_animation_node("child", orientation_values=[[0.0, 0.0, 0.0, 1.0]])],
    )

    pose = evaluate_aurora_animation_pose(model, animation, 0.0)

    _assert_quat_equivalent(pose.local_transforms_by_node["child"].rotation, (0.0, 0.0, 0.0, 1.0))


def test_position_controller_is_absolute_local_not_delta() -> None:
    model = _two_node_model(child_position=(1.0, 0.0, 0.0))
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[_animation_node("child", position_values=[[2.0, 0.0, 0.0]])],
    )

    pose = evaluate_aurora_animation_pose(model, animation, 0.0)

    assert pose.local_transforms_by_node["child"].position == pytest.approx((2.0, 0.0, 0.0))


def test_unkeyed_components_fall_back_to_rest() -> None:
    model = _two_node_model(child_position=(1.0, 2.0, 3.0), child_rotation=_quat_axis("Y", 45.0))
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            _animation_node("child", orientation_values=[list(_quat_axis("Z", 10.0))]),
            _animation_node("root", position_values=[[4.0, 5.0, 6.0]]),
        ],
    )

    pose = evaluate_aurora_animation_pose(model, animation, 0.0)

    assert pose.local_transforms_by_node["child"].position == pytest.approx((1.0, 2.0, 3.0))
    _assert_quat_equivalent(pose.local_transforms_by_node["child"].rotation, _quat_axis("Z", 10.0))
    _assert_quat_equivalent(pose.local_transforms_by_node["root"].rotation, (0.0, 0.0, 0.0, 1.0))


def test_quaternion_hemisphere_continuity_uses_shortest_path() -> None:
    model = _two_node_model()
    q10 = _quat_axis("Z", 10.0)
    q20_flipped = _quat_neg(_quat_axis("Z", 20.0))
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            _animation_node(
                "root",
                orientation_values=[list(q10), list(q20_flipped)],
                times=[0.0, 1.0],
            )
        ],
    )

    pose = evaluate_aurora_animation_pose(model, animation, 0.5)
    q = pose.local_transforms_by_node["root"].rotation
    norm = math.sqrt(sum(value * value for value in q))
    yaw_degrees = abs(math.degrees(2.0 * math.atan2(q[2], q[3])))

    assert norm == pytest.approx(1.0, abs=1e-6)
    assert yaw_degrees == pytest.approx(15.0, abs=1.0)


def test_validator_rejects_unknown_controller_node() -> None:
    model = _two_node_model()
    animation = Animation(
        name="pause1",
        length=1.0,
        nodes=[
            _animation_node(
                "UE_Mannequin_ThighTwist_01",
                orientation_values=[[0.0, 0.0, 0.0, 1.0]],
            )
        ],
    )

    report = validate_animation_block_against_model(model, animation)

    assert report.success is False
    with pytest.raises(AnimationBlockValidationError) as exc:
        report.raise_for_errors(animation.name, model.name)
    assert "UE_Mannequin_ThighTwist_01" in str(exc.value)
    assert "KOTOR animation controllers must target existing Aurora nodes" in str(exc.value)


def test_export_path_validates_structure_before_writer(monkeypatch, tmp_path: Path) -> None:
    target_model = KotorModel(name="pmbam", animations=[Animation(name="pause1", length=1.0)])
    request = _request(tmp_path, "pause1")
    writer_called = False

    class SpyWriter:
        def write_files(self, *_args, **_kwargs):
            nonlocal writer_called
            writer_called = True

    invalid_animation = Animation(
        name="UE_Idle",
        length=1.0,
        nodes=[
            _animation_node(
                "UE_Mannequin_ThighTwist_01",
                orientation_values=[[0.0, 0.0, 0.0, 1.0]],
            )
        ],
    )

    monkeypatch.setattr(AuroraAnimationWriter, "_load_model", lambda self, req: target_model)
    monkeypatch.setattr(
        AuroraAnimationWriter,
        "build_animation_from_r3a",
        lambda self, **_kwargs: invalid_animation,
    )
    monkeypatch.setattr(
        "src.core.retargeting.aurora_animation_writer.MDLBinaryWriter",
        lambda: SpyWriter(),
    )

    result = AuroraAnimationWriter().inject(request)

    assert result.success is False
    assert writer_called is False
    assert not request.output_mdl.exists()
    assert not request.output_mdl.with_suffix(".mdx").exists()
    assert not request.output_manifest.exists()
    assert "unknown controller node 'UE_Mannequin_ThighTwist_01'" in result.errors[0]


def _request(tmp_path: Path, slot: str) -> AuroraAnimationInjectionRequest:
    r3a = tmp_path / "clip.json"
    r3a.write_text(json.dumps({"frame_count": 1, "target_curves": {}}), encoding="utf-8")
    target = tmp_path / "target.mdl"
    target.write_bytes(b"minimal target")
    return AuroraAnimationInjectionRequest(
        r3a_animation_json=r3a,
        target_mdl=target,
        animation_slot=slot,
        output_mdl=tmp_path / "out" / "target.mdl",
        output_manifest=tmp_path / "out" / "manifest.json",
    )
