"""Core KOTOR-to-Unreal Retarget Workbench preview/solver tests."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from src.core.retargeting.kotor_source_animation import (
    KotorAnimationSourceReport,
    KotorAnimationSourceRequest,
    KotorAnimationSourceResult,
)
from src.core.retargeting.kotor_to_unreal_preview import (
    KotorToUnrealPreviewRequest,
    build_kotor_to_unreal_preview,
)
from src.core.retargeting.kotor_to_unreal_solver import (
    retarget_kotor_source_clip_to_unreal_animation,
    validate_retarget_profile_for_unreal_target,
)
from src.core.retargeting.retarget_output_naming import RetargetOutputNaming
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
)
from src.core.retargeting.unreal_target_skeleton import UnrealSkeletonNode, UnrealTargetSkeleton
from src.core.validation.validation_bus import ValidationReport


def _quat_z(degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    return (0.0, 0.0, math.sin(radians / 2.0), math.cos(radians / 2.0))


def _compose(parent: Transform, child: Transform) -> Transform:
    return Transform.from_matrix(parent.to_matrix() @ child.to_matrix())


def _source_clip(*, child_moves: bool = False, root_moves: bool = False) -> SourceSkeletonClip:
    root_rest = Transform()
    child_rest_local = Transform(position=(1.0, 0.0, 0.0))
    child_rest_global = _compose(root_rest, child_rest_local)
    root_node = SourceSkeletonNode("root", None, 0, root_rest, root_rest, "root")
    child_node = SourceSkeletonNode("child", "root", 1, child_rest_local, child_rest_global, "deform")
    rest_pose = SourcePose(
        time_seconds=0.0,
        local_transforms={"root": root_rest, "child": child_rest_local},
        global_transforms={"root": root_rest, "child": child_rest_global},
    )
    root_t1 = Transform(
        position=(5.0, 0.0, 0.0) if root_moves else (0.0, 0.0, 0.0),
        rotation=_quat_z(90.0),
    )
    child_local_t1 = Transform(position=(2.0, 0.0, 0.0) if child_moves else (1.0, 0.0, 0.0))
    child_global_t1 = _compose(root_t1, child_local_t1)
    pose1 = SourcePose(
        time_seconds=1.0,
        local_transforms={"root": root_t1, "child": child_local_t1},
        global_transforms={"root": root_t1, "child": child_global_t1},
    )
    return SourceSkeletonClip(
        source_path="kotor://pmbam",
        clip_name="pause1",
        duration_seconds=1.0,
        sample_rate=1.0,
        nodes=[root_node, child_node],
        rest_pose=rest_pose,
        sampled_poses=[rest_pose, pose1],
        axis_system="kotor_aurora",
    )


def _target_skeleton(*, special: bool = False) -> UnrealTargetSkeleton:
    root = UnrealSkeletonNode("root", None, 0, Transform(), Transform(), "root")
    child_local = Transform(position=(1.0, 0.0, 0.0))
    child = UnrealSkeletonNode("child", "root", 1, child_local, _compose(root.rest_global, child_local), "deform")
    nodes = [root, child]
    if special:
        twist_local = Transform(position=(0.25, 0.0, 0.0))
        twist = UnrealSkeletonNode(
            "lowerarm_twist_01_l",
            "child",
            2,
            twist_local,
            _compose(child.rest_global, twist_local),
            "twist",
        )
        ik = UnrealSkeletonNode("ik_foot_root", "root", 3, Transform(), Transform(), "ik")
        nodes.extend([twist, ik])
    return UnrealTargetSkeleton(name="UE5 Manny", nodes=nodes)


def _profile(*, target_name: str = "child") -> RetargetProfile:
    return RetargetProfile(
        name="pmbam_to_manny",
        mappings=[
            RetargetMappingEntry(role="root", source_node="root", target_node="root"),
            RetargetMappingEntry(role="spine", source_node="child", target_node=target_name),
        ],
    )


def test_kotor_source_samples_then_ue_solver_builds_clip(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, object]] = []
    source_clip = _source_clip()
    sample_result = KotorAnimationSourceResult(
        source_clip=source_clip,
        resolved_slot=SimpleNamespace(slot_name="pause1"),
        report=KotorAnimationSourceReport("pmbam", "pause1", None, 1.0, 2, 2, 1, False),
    )
    target = _target_skeleton()

    def fake_sample(request: KotorAnimationSourceRequest):
        calls.append(("sample", request))
        return sample_result

    def fake_solver(**kwargs):
        calls.append(("solver", SimpleNamespace(**kwargs)))
        from src.core.retargeting.unreal_target_skeleton import UnrealAnimationClip

        return UnrealAnimationClip("pmbam_pause1_export", 1.0, 30.0, target.name, [])

    monkeypatch.setattr("src.core.retargeting.kotor_to_unreal_preview.sample_kotor_animation_slot_as_source_clip", fake_sample)
    monkeypatch.setattr("src.core.retargeting.kotor_to_unreal_preview.retarget_kotor_source_clip_to_unreal_animation", fake_solver)
    monkeypatch.setattr(
        "src.core.retargeting.kotor_to_unreal_preview.audit_unreal_animation_clip",
        lambda *_args, **_kwargs: ValidationReport(source="fake.audit"),
    )

    result = build_kotor_to_unreal_preview(
        KotorToUnrealPreviewRequest(
            source_model=SimpleNamespace(name="pmbam"),
            source_animation_slot="pause1",
            target_skeleton=target,
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(unreal_clip_name="pmbam_pause1_export"),
        )
    )

    assert [name for name, _ in calls] == ["sample", "solver"]
    assert calls[0][1].animation_slot == "pause1"
    assert calls[1][1].source_clip is source_clip
    assert calls[1][1].target_skeleton is target
    assert result.animation_clip.clip_name == "pmbam_pause1_export"


def test_ue_clip_name_is_separate_from_source_kotor_animation(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}
    sample_result = KotorAnimationSourceResult(
        source_clip=_source_clip(),
        resolved_slot=SimpleNamespace(slot_name="pause1"),
        report=KotorAnimationSourceReport("pmbam", "pause1", None, 1.0, 2, 2, 1, False),
    )

    def fake_sample(request: KotorAnimationSourceRequest):
        seen["source_slot"] = request.animation_slot
        return sample_result

    monkeypatch.setattr("src.core.retargeting.kotor_to_unreal_preview.sample_kotor_animation_slot_as_source_clip", fake_sample)

    result = build_kotor_to_unreal_preview(
        KotorToUnrealPreviewRequest(
            source_model=SimpleNamespace(name="pmbam"),
            source_animation_slot="pause1",
            target_skeleton=_target_skeleton(),
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(unreal_clip_name="pmbam_pause1_export"),
            source_sample_rate=1.0,
        )
    )

    assert seen["source_slot"] == "pause1"
    assert result.animation_clip.clip_name == "pmbam_pause1_export"


@pytest.mark.parametrize("clip_name", ["", "bad/name", "bad\\name"])
def test_invalid_or_missing_ue_clip_name_blocks_preview(clip_name: str) -> None:
    with pytest.raises(Exception, match="UE animation clip name|requires a UE animation clip name"):
        build_kotor_to_unreal_preview(
            KotorToUnrealPreviewRequest(
                source_model=SimpleNamespace(name="pmbam"),
                source_animation_slot="pause1",
                target_skeleton=_target_skeleton(),
                retarget_profile=_profile(),
                output_naming=RetargetOutputNaming(unreal_clip_name=clip_name),
            )
        )


def test_same_hierarchy_identity_retarget_creates_expected_ue_local_keys() -> None:
    clip = retarget_kotor_source_clip_to_unreal_animation(
        source_clip=_source_clip(),
        target_skeleton=_target_skeleton(),
        profile=_profile(),
        output_clip_name="pmbam_pause1",
        sample_rate=1.0,
    )

    pose = clip.poses[-1]
    assert pose.local_transforms["root"].rotation == pytest.approx(_quat_z(90.0), abs=1e-5)
    assert pose.local_transforms["child"].position == pytest.approx((1.0, 0.0, 0.0), abs=1e-5)
    assert pose.global_transforms["child"].position == pytest.approx((0.0, 1.0, 0.0), abs=1e-5)


def test_non_root_kotor_translations_are_ignored() -> None:
    clip = retarget_kotor_source_clip_to_unreal_animation(
        source_clip=_source_clip(child_moves=True),
        target_skeleton=_target_skeleton(),
        profile=_profile(),
        output_clip_name="pmbam_pause1",
        sample_rate=1.0,
    )

    assert clip.poses[-1].local_transforms["child"].position == pytest.approx((1.0, 0.0, 0.0), abs=1e-5)


def test_root_motion_stripped_by_default() -> None:
    clip = retarget_kotor_source_clip_to_unreal_animation(
        source_clip=_source_clip(root_moves=True),
        target_skeleton=_target_skeleton(),
        profile=_profile(),
        output_clip_name="pmbam_pause1",
        sample_rate=1.0,
    )

    assert clip.poses[-1].local_transforms["root"].position == pytest.approx((0.0, 0.0, 0.0), abs=1e-5)


def test_ue_twist_ik_helper_bones_preserved_at_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _target_skeleton(special=True)
    monkeypatch.setattr(
        "src.core.retargeting.kotor_to_unreal_preview.sample_kotor_animation_slot_as_source_clip",
        lambda _request: KotorAnimationSourceResult(
            source_clip=_source_clip(),
            resolved_slot=SimpleNamespace(slot_name="pause1"),
            report=KotorAnimationSourceReport("pmbam", "pause1", None, 1.0, 2, 2, 1, False),
        ),
    )
    result = build_kotor_to_unreal_preview(
        KotorToUnrealPreviewRequest(
            source_model=SimpleNamespace(name="pmbam"),
            source_animation_slot="pause1",
            target_skeleton=target,
            retarget_profile=_profile(),
            output_naming=RetargetOutputNaming(unreal_clip_name="pmbam_pause1"),
            source_sample_rate=1.0,
        )
    )

    pose = result.animation_clip.poses[-1]
    assert pose.local_transforms["lowerarm_twist_01_l"].position == pytest.approx((0.25, 0.0, 0.0), abs=1e-5)
    assert pose.local_transforms["ik_foot_root"].position == pytest.approx((0.0, 0.0, 0.0), abs=1e-5)
    assert any("twist/IK/helper bones" in warning for warning in result.warnings)


def test_profile_validation_rejects_unknown_ue_target_bone() -> None:
    report = validate_retarget_profile_for_unreal_target(
        _profile(target_name="MissingUEBone"),
        _source_clip(),
        _target_skeleton(),
    )

    assert report.has_blocking
    assert any("MissingUEBone" in issue.message for issue in report.issues)
