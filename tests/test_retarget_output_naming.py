"""Retarget output animation naming policy tests."""

from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.animation.animation_engine import SuperModelResolver
from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.aurora_animation_writer import (
    AuroraAnimationInjectionResult,
    prepare_local_animation_override_for_export,
)
from src.core.retargeting.retarget_modes import RetargetMode
from src.core.retargeting.retarget_output_naming import (
    KotorOutputAnimationNameMode,
    RetargetOutputNaming,
    RetargetOutputNamingError,
    resolve_retarget_output_name,
    validate_custom_kotor_animation_name,
)
from src.core.retargeting.retarget_preview import RetargetPreviewRequest, build_retarget_preview
from src.core.retargeting.retarget_preview_export import (
    RetargetPreviewExportRequest,
    export_retarget_preview_override,
)
from src.core.retargeting.retarget_profile import RetargetMappingEntry, RetargetProfile
from src.core.retargeting.source_animation import (
    SourcePose,
    SourceSkeletonClip,
    SourceSkeletonNode,
    Transform,
)


def _quat_axis(axis: str, degrees: float) -> tuple[float, float, float, float]:
    radians = math.radians(degrees)
    s = math.sin(radians / 2.0)
    c = math.cos(radians / 2.0)
    if axis.upper() == "Z":
        return (0.0, 0.0, s, c)
    raise ValueError(axis)


def _source_clip() -> SourceSkeletonClip:
    poses = [
        SourcePose(
            time_seconds=0.0,
            global_transforms={"root": Transform()},
            local_transforms={"root": Transform()},
        ),
        SourcePose(
            time_seconds=1.0,
            global_transforms={"root": Transform(rotation=_quat_axis("Z", 20.0))},
            local_transforms={"root": Transform(rotation=_quat_axis("Z", 20.0))},
        ),
    ]
    node = SourceSkeletonNode(
        name="root",
        parent_name=None,
        index=0,
        rest_local=poses[0].local_transforms["root"],
        rest_global=poses[0].global_transforms["root"],
        classification="root",
    )
    return SourceSkeletonClip(
        source_path="source.fbx",
        clip_name="RunForward",
        duration_seconds=1.0,
        sample_rate=30.0,
        nodes=[node],
        rest_pose=poses[0],
        sampled_poses=poses,
        axis_system="TEST",
        unit_scale_to_meters=1.0,
    )


def _target_model(tmp_path: Path | None = None, *, anims: tuple[str, ...] = ("pause1",)) -> KotorModel:
    mdl_path = None
    mdx_path = None
    if tmp_path is not None:
        mdl = tmp_path / "pmbam.mdl"
        mdx = tmp_path / "pmbam.mdx"
        mdl.write_bytes(b"target mdl")
        mdx.write_bytes(b"target mdx")
        mdl_path = str(mdl)
        mdx_path = str(mdx)
    return KotorModel(
        name="pmbam",
        root_node=ModelNode(name="root"),
        animations=[Animation(name=name, length=1.0) for name in anims],
        mdl_path=mdl_path,
        mdx_path=mdx_path,
    )


def _profile(slot: str = "pause1") -> RetargetProfile:
    return RetargetProfile(
        name="naming_profile",
        animation_slot=slot,
        source_reference={"mode": "clip_rest"},
        target_reference={"mode": "target_rest"},
        mappings=[RetargetMappingEntry(source_node="root", target_node="root", role="root")],
    )


@pytest.fixture(autouse=True)
def _clear_supermodel_resolver():
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)
    yield
    SuperModelResolver.clear_cache()
    SuperModelResolver.configure(None)


def test_vanilla_mode_still_requires_valid_target_slot() -> None:
    target = _target_model(anims=("pause1", "walk"))

    resolved = resolve_retarget_output_name(
        workbench_mode=RetargetMode.UNREAL_TO_KOTOR,
        naming=RetargetOutputNaming(requested_kotor_animation_name="pause1"),
        target_model=target,
    )

    assert resolved.animation_block_name == "pause1"
    assert resolved.requires_custom_animation_patch is False
    with pytest.raises(RetargetOutputNamingError, match="Switch to Custom animation patch mode"):
        resolve_retarget_output_name(
            workbench_mode=RetargetMode.UNREAL_TO_KOTOR,
            naming=RetargetOutputNaming(requested_kotor_animation_name="gr_spin_attack_01"),
            target_model=target,
        )


def test_custom_patch_mode_accepts_non_stock_name_and_preserves_case() -> None:
    target = _target_model(anims=("pause1",))

    resolved = resolve_retarget_output_name(
        workbench_mode=RetargetMode.UNREAL_TO_KOTOR,
        naming=RetargetOutputNaming(
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_kotor_animation_name="GR_SpinAttack_01",
        ),
        target_model=target,
    )

    assert resolved.animation_block_name == "GR_SpinAttack_01"
    assert resolved.requires_custom_animation_patch is True


@pytest.mark.parametrize("bad_name", ["", ".", "..", "foo/bar", "foo\\bar", "bad\nname", "bad\tname"])
def test_custom_patch_mode_rejects_unsafe_names(bad_name: str) -> None:
    with pytest.raises(RetargetOutputNamingError):
        validate_custom_kotor_animation_name(bad_name)


def test_display_label_never_becomes_animation_block_name() -> None:
    resolved = resolve_retarget_output_name(
        workbench_mode=RetargetMode.UNREAL_TO_KOTOR,
        naming=RetargetOutputNaming(
            kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requested_kotor_animation_name="gr_spin_attack_01",
            display_label="My Cool Spin Attack",
        ),
        target_model=_target_model(),
    )

    assert resolved.animation_block_name == "gr_spin_attack_01"
    assert resolved.display_label == "My Cool Spin Attack"


def test_preview_custom_output_name_uses_profile_copy_without_mutating_profile() -> None:
    profile = _profile(slot="pause1")
    preview = build_retarget_preview(
        RetargetPreviewRequest(
            source_clip=_source_clip(),
            target_model=_target_model(),
            profile=profile,
            output_naming=RetargetOutputNaming(
                kotor_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
                requested_kotor_animation_name="gr_spin_attack_01",
                display_label="Spin attack test",
            ),
        )
    )

    assert profile.animation_slot == "pause1"
    assert preview.animation_block.name == "gr_spin_attack_01"
    assert preview.output_name_mode == KotorOutputAnimationNameMode.CUSTOM_PATCH
    assert preview.requires_custom_animation_patch is True
    assert preview.output_display_label == "Spin attack test"
    assert any("custom animation patch/runtime" in warning for warning in preview.warnings)


def test_export_prepare_custom_output_bypasses_vanilla_slot_resolution() -> None:
    target = _target_model(anims=("pause1",))
    prepared, resolved = prepare_local_animation_override_for_export(
        target,
        Animation(name="source_clip", length=1.0),
        "gr_spin_attack_01",
        kotor_output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
    )

    assert prepared.name == "gr_spin_attack_01"
    assert resolved.slot_name == "gr_spin_attack_01"
    assert resolved.inherited is False


def test_invalid_custom_export_name_blocks_before_write(tmp_path: Path) -> None:
    target = _target_model(tmp_path)
    preview = SimpleNamespace(
        animation_block=Animation(name="foo/bar", length=1.0, nodes=[ModelNode(name="root")]),
        slot_name="foo/bar",
        preview_audit=SimpleNamespace(passed=True),
        output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        requires_custom_animation_patch=True,
        warnings=[],
    )
    writer = SimpleNamespace(inject_animation_block=lambda *_args, **_kwargs: pytest.fail("writer must not run"))

    with pytest.raises(RetargetOutputNamingError):
        export_retarget_preview_override(
            RetargetPreviewExportRequest(
                preview_result=preview,
                original_target_model=target,
                output_mdl_path=tmp_path / "out" / "pmbam.mdl",
                output_mdx_path=tmp_path / "out" / "pmbam.mdx",
                kotor_output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
                requires_custom_animation_patch=True,
            ),
            writer=writer,
        )


def test_export_manifest_metadata_records_custom_patch_requirement(tmp_path: Path) -> None:
    target = _target_model(tmp_path)
    preview = SimpleNamespace(
        animation_block=Animation(name="gr_spin_attack_01", length=1.0, nodes=[ModelNode(name="root")]),
        slot_name="gr_spin_attack_01",
        preview_audit=SimpleNamespace(passed=True),
        output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
        requires_custom_animation_patch=True,
        warnings=[],
    )

    class SpyWriter:
        def inject_animation_block(self, request, animation_block):
            request.output_mdl.write_bytes(b"mdl")
            request.output_mdl.with_suffix(".mdx").write_bytes(b"mdx")
            request.output_manifest.write_text("{}\n", encoding="utf-8")
            return AuroraAnimationInjectionResult(
                success=True,
                animation_slot=request.animation_slot,
                output_mdl=request.output_mdl,
                output_mdx=request.output_mdl.with_suffix(".mdx"),
                manifest_path=request.output_manifest,
                kotor_output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH.value,
                requires_custom_animation_patch=True,
                vanilla_slot_safe=False,
            )

    result = export_retarget_preview_override(
        RetargetPreviewExportRequest(
            preview_result=preview,
            original_target_model=target,
            output_mdl_path=tmp_path / "out" / "pmbam.mdl",
            output_mdx_path=tmp_path / "out" / "pmbam.mdx",
            kotor_output_name_mode=KotorOutputAnimationNameMode.CUSTOM_PATCH,
            requires_custom_animation_patch=True,
        ),
        writer=SpyWriter(),
    )

    assert result.export_job_result is not None
    assert result.export_job_result.metadata["kotor_output_name_mode"] == "custom_patch"
    assert result.export_job_result.metadata["animation_name"] == "gr_spin_attack_01"
    assert result.export_job_result.metadata["requires_custom_animation_patch"] is True
    assert result.export_job_result.metadata["vanilla_slot_safe"] is False
