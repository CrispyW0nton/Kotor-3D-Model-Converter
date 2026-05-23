"""Core KOTOR-to-KOTOR Retarget Workbench preview adapter tests."""

from __future__ import annotations

import copy
import math
from types import SimpleNamespace

import pytest

from src.core.animation.animation_engine import SuperModelResolver, evaluate_aurora_animation_pose
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.kotor_source_animation import (
    KotorAnimationSourceError,
    KotorAnimationSourceReport,
    KotorAnimationSourceRequest,
    KotorAnimationSourceResult,
)
from src.core.retargeting.kotor_to_kotor_preview import (
    KotorToKotorPreviewRequest,
    build_kotor_to_kotor_retarget_preview,
)
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
)
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import SourceSkeletonClip, SourceSkeletonNode, SourcePose, Transform


def _quat_axis(axis: str, degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    s = math.sin(radians / 2.0)
    c = math.cos(radians / 2.0)
    if axis.upper() == "Z":
        return (0.0, 0.0, s, c)
    raise ValueError(axis)


def _animation_node(name: str, values: list[list[float]], times: list[float] | None = None) -> ModelNode:
    return ModelNode(
        name=name,
        controllers=[
            {
                "type": 20,
                "name": "orientation",
                "columns": 4,
                "times": times or [0.0],
                "values": values,
            }
        ],
    )


def _two_node_model(*, name: str = "pmbam", animations: list[Animation] | None = None, supermodel: str = "NULL") -> KotorModel:
    root = ModelNode(name="root")
    child = ModelNode(name="child", position=(1.0, 0.0, 0.0), parent=root)
    root.children.append(child)
    return KotorModel(name=name, supermodel=supermodel, root_node=root, animations=animations or [])


def _anim(name: str = "pause1", *, nodes: list[ModelNode] | None = None) -> Animation:
    return Animation(name=name, length=1.0, nodes=nodes or [], anim_root="root")


def _profile(slot: str = "pause1") -> RetargetProfile:
    return RetargetProfile(
        name="kotor_to_kotor_profile",
        animation_slot=slot,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=[RetargetMappingEntry(source_node="root", target_node="root", role="root")],
    )


def _fake_source_clip() -> SourceSkeletonClip:
    pose = SourcePose(time_seconds=0.0, global_transforms={"root": Transform()}, local_transforms={"root": Transform()})
    node = SourceSkeletonNode("root", None, 0, pose.local_transforms["root"], pose.global_transforms["root"], "root")
    return SourceSkeletonClip("fake", "pause1", 0.0, 30.0, [node], pose, [pose], axis_system="kotor_aurora")


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_adapter_samples_source_then_builds_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    sample_result = KotorAnimationSourceResult(
        source_clip=_fake_source_clip(),
        resolved_slot=SimpleNamespace(slot_name="pause1"),
        report=KotorAnimationSourceReport("src", "pause1", None, 0.0, 1, 1, 0, False),
    )
    preview_result = SimpleNamespace(slot_name="walk", warnings=["preview warning"])

    def fake_sample(request: KotorAnimationSourceRequest):
        calls.append(("sample", request))
        return sample_result

    def fake_preview(request):
        calls.append(("preview", request))
        return preview_result

    monkeypatch.setattr("src.core.retargeting.kotor_to_kotor_preview.sample_kotor_animation_slot_as_source_clip", fake_sample)
    monkeypatch.setattr("src.core.retargeting.kotor_to_kotor_preview.build_retarget_preview", fake_preview)

    result = build_kotor_to_kotor_retarget_preview(
        KotorToKotorPreviewRequest(
            source_model=SimpleNamespace(name="source"),
            source_animation_slot="pause1",
            target_model=SimpleNamespace(name="target"),
            retarget_profile=_profile("walk"),
            output_naming=RetargetOutputNaming(requested_kotor_animation_name="walk"),
        )
    )

    assert [name for name, _ in calls] == ["sample", "preview"]
    assert calls[0][1].source_model.name == "source"
    assert calls[0][1].animation_slot == "pause1"
    assert calls[1][1].source_clip is sample_result.source_clip
    assert calls[1][1].target_model.name == "target"
    assert calls[1][1].output_naming.requested_kotor_animation_name == "walk"
    assert result.preview_result is preview_result


def test_invalid_source_animation_fails_before_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.core.retargeting.kotor_to_kotor_preview.sample_kotor_animation_slot_as_source_clip",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KotorAnimationSourceError("missing_source_anim")),
    )
    monkeypatch.setattr(
        "src.core.retargeting.kotor_to_kotor_preview.build_retarget_preview",
        lambda *_args, **_kwargs: pytest.fail("preview must not run after source sampling failure"),
    )

    with pytest.raises(KotorAnimationSourceError, match="missing_source_anim"):
        build_kotor_to_kotor_retarget_preview(
            KotorToKotorPreviewRequest(
                source_model=SimpleNamespace(),
                source_animation_slot="missing_source_anim",
                target_model=SimpleNamespace(),
                retarget_profile=_profile(),
            )
        )


def test_invalid_vanilla_target_slot_fails_through_preview() -> None:
    source = _two_node_model(animations=[_anim(nodes=[_animation_node("root", [[0.0, 0.0, 0.0, 1.0]])])])
    target = _two_node_model(animations=[_anim("pause1")])

    with pytest.raises(Exception, match="Switch to Custom animation patch mode"):
        build_kotor_to_kotor_retarget_preview(
            KotorToKotorPreviewRequest(
                source_model=source,
                source_animation_slot="pause1",
                target_model=target,
                retarget_profile=_profile(),
                output_naming=RetargetOutputNaming(requested_kotor_animation_name="NotARealSlot"),
            )
        )


def test_custom_target_output_name_works_and_keeps_source_slot_separate() -> None:
    source = _two_node_model(animations=[_anim(nodes=[_animation_node("root", [[0.0, 0.0, 0.0, 1.0]])])])
    target = _two_node_model(animations=[_anim("pause1")])

    result = build_kotor_to_kotor_retarget_preview(
        KotorToKotorPreviewRequest(
            source_model=source,
            source_animation_slot="pause1",
            target_model=target,
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(
                kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
                requested_kotor_animation_name="gr_bek_rally",
            ),
        )
    )

    assert result.source_sample_result.source_clip.clip_name == "pause1"
    assert result.preview_result.animation_block.name == "gr_bek_rally"
    assert result.preview_result.requires_custom_animation_patch is True
    assert any("custom animation patch/runtime" in warning for warning in result.warnings)


def test_same_hierarchy_pass_through_evaluates_expected_pose() -> None:
    source = _two_node_model(
        animations=[
            _anim(nodes=[_animation_node("root", [[0.0, 0.0, 0.0, 1.0], list(_quat_axis("Z", 90.0))], [0.0, 1.0])])
        ]
    )
    target = _two_node_model(animations=[_anim("pause1")])

    result = build_kotor_to_kotor_retarget_preview(
        KotorToKotorPreviewRequest(
            source_model=source,
            source_animation_slot="pause1",
            target_model=target,
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(requested_kotor_animation_name="pause1"),
            source_sample_rate=1.0,
        )
    )
    pose = evaluate_aurora_animation_pose(result.preview_result.preview_model, result.preview_result.animation_block, 1.0)

    assert pose.local_transforms_by_node["root"].rotation == pytest.approx(_quat_axis("Z", 90.0), abs=1e-5)
    assert pose.world_transforms_by_node["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-5)


def test_inherited_source_animation_works() -> None:
    inherited = _anim(nodes=[_animation_node("root", [list(_quat_axis("Z", 45.0))])])
    super_model = _two_node_model(name="S_Test", animations=[inherited])
    SuperModelResolver.prime_cache("S_Test", super_model)
    source = _two_node_model(supermodel="S_Test")
    target = _two_node_model(animations=[_anim("pause1")])

    result = build_kotor_to_kotor_retarget_preview(
        KotorToKotorPreviewRequest(
            source_model=source,
            source_animation_slot="pause1",
            target_model=target,
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(requested_kotor_animation_name="pause1"),
        )
    )

    assert result.source_sample_result.report.inherited_from_supermodel is True
    assert result.preview_result.slot_name == "pause1"


def test_preview_does_not_mutate_inputs() -> None:
    source = _two_node_model(animations=[_anim(nodes=[_animation_node("root", [[0.0, 0.0, 0.0, 1.0]])])])
    target = _two_node_model(animations=[_anim("pause1")])
    profile = _profile()
    naming = RetargetOutputNaming(
        kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        requested_kotor_animation_name="gr_bek_rally",
    )
    before_source = copy.deepcopy(source)
    before_target = copy.deepcopy(target)
    before_profile = copy.deepcopy(profile)
    before_naming = copy.deepcopy(naming)

    build_kotor_to_kotor_retarget_preview(
        KotorToKotorPreviewRequest(source, "pause1", target, profile, output_naming=naming)
    )

    assert [node.name for node in source.all_nodes()] == [node.name for node in before_source.all_nodes()]
    assert [node.name for node in target.all_nodes()] == [node.name for node in before_target.all_nodes()]
    assert [anim.name for anim in target.animations] == [anim.name for anim in before_target.animations]
    assert profile == before_profile
    assert naming == before_naming
