"""Export gate for the last successful GhostRigger retarget preview."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.geometry.model_data import Animation, KotorModel, ModelNode
from src.core.retargeting.aurora_animation_writer import AuroraAnimationInjectionResult
from src.core.retargeting.retarget_preview_export import (
    RetargetPreviewExportError,
    RetargetPreviewExportRequest,
    export_retarget_preview_override,
)


def _anim(name: str = "pause1") -> Animation:
    return Animation(
        name=name,
        length=1.0,
        anim_root="root",
        nodes=[
            ModelNode(
                name="root",
                controllers=[
                    {
                        "type": 20,
                        "name": "orientation",
                        "columns": 4,
                        "times": [0.0],
                        "values": [[0.0, 0.0, 0.0, 1.0]],
                    }
                ],
            )
        ],
    )


def _target(tmp_path: Path, *, name: str = "pmbam") -> KotorModel:
    mdl_path = tmp_path / f"{name}.mdl"
    mdx_path = tmp_path / f"{name}.mdx"
    mdl_path.write_bytes(b"target mdl")
    mdx_path.write_bytes(b"target mdx")
    return KotorModel(
        name=name,
        root_node=ModelNode(name="root"),
        animations=[Animation(name="pause1", length=1.0)],
        mdl_path=str(mdl_path),
        mdx_path=str(mdx_path),
    )


def _preview(*, passed: bool = True, slot: str = "pause1"):
    return SimpleNamespace(
        animation_block=_anim(slot),
        slot_name=slot,
        preview_audit=SimpleNamespace(passed=passed),
        warnings=[],
    )


def _request(tmp_path: Path, *, preview=None, target=None, overwrite: bool = True) -> RetargetPreviewExportRequest:
    return RetargetPreviewExportRequest(
        preview_result=preview or _preview(),
        original_target_model=target or _target(tmp_path),
        output_mdl_path=tmp_path / "out" / "pmbam.mdl",
        output_mdx_path=tmp_path / "out" / "pmbam.mdx",
        overwrite=overwrite,
    )


class SpyWriter:
    def __init__(
        self,
        *,
        success: bool = True,
        mutate_model: bool = False,
        expected_final_mdl: Path | None = None,
        expected_source_mdl_bytes: bytes | None = None,
        expected_source_mdx_bytes: bytes | None = None,
    ) -> None:
        self.success = success
        self.mutate_model = mutate_model
        self.expected_final_mdl = expected_final_mdl
        self.expected_source_mdl_bytes = expected_source_mdl_bytes
        self.expected_source_mdx_bytes = expected_source_mdx_bytes
        self.calls: list[tuple[object, Animation]] = []

    def inject_animation_block(self, request, animation_block: Animation):
        self.calls.append((request, animation_block))
        if self.expected_final_mdl is not None:
            assert request.output_mdl != self.expected_final_mdl
            assert not self.expected_final_mdl.exists()
            assert request.output_mdl.parent.name.startswith(".ghostrigger_export_")
        if self.expected_source_mdl_bytes is not None:
            assert request.target_mdl.read_bytes() == self.expected_source_mdl_bytes
        if self.expected_source_mdx_bytes is not None:
            assert request.target_mdx is not None
            assert request.target_mdx.read_bytes() == self.expected_source_mdx_bytes
        if self.mutate_model:
            request.target_model_override.animations.append(Animation(name="mutated", length=1.0))
            animation_block.name = "mutated"
        request.output_mdl.write_bytes(b"out mdl")
        request.output_mdl.with_suffix(".mdx").write_bytes(b"out mdx")
        request.output_manifest.write_text("{}\n", encoding="utf-8")
        return AuroraAnimationInjectionResult(
            success=self.success,
            output_mdl=request.output_mdl,
            output_mdx=request.output_mdl.with_suffix(".mdx"),
            manifest_path=request.output_manifest,
            animation_slot=request.animation_slot,
            warnings=["writer warning"] if self.success else [],
            errors=[] if self.success else [
                "Exported retarget preview failed MDL readback verification: slot 'pause1'"
            ],
        )


def test_export_uses_last_preview_animation_block_without_retargeting(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "src.core.retargeting.retarget_solver.retarget_source_clip_to_aurora_animation",
        lambda *_args, **_kwargs: pytest.fail("export must not rerun the retarget solver"),
    )
    monkeypatch.setattr(
        "src.core.retargeting.retarget_preview.build_retarget_preview",
        lambda *_args, **_kwargs: pytest.fail("export must not rebuild preview"),
    )
    writer = SpyWriter()
    resource_manager = object()
    request = _request(tmp_path)
    request.resource_manager = resource_manager

    result = export_retarget_preview_override(request, writer=writer)

    assert result.slot_name == "pause1"
    assert len(writer.calls) == 1
    injection_request, animation_block = writer.calls[0]
    assert injection_request.animation_slot == "pause1"
    assert injection_request.verify_roundtrip is True
    assert injection_request.resource_manager is resource_manager
    assert animation_block.name == "pause1"
    assert result.export_job_result is not None
    assert result.export_job_result.succeeded is True


def test_failed_preview_audit_blocks_export_before_write(tmp_path: Path) -> None:
    writer = SpyWriter()
    request = _request(tmp_path, preview=_preview(passed=False))

    with pytest.raises(RetargetPreviewExportError, match="audit did not pass"):
        export_retarget_preview_override(request, writer=writer)

    assert writer.calls == []
    assert not request.output_mdl_path.exists()
    assert not request.output_mdx_path.exists()


def test_verify_roundtrip_defaults_true(tmp_path: Path) -> None:
    writer = SpyWriter()

    export_retarget_preview_override(_request(tmp_path), writer=writer)

    injection_request, _animation_block = writer.calls[0]
    assert injection_request.verify_roundtrip is True


def test_export_uses_staged_paths_before_final_promotion(tmp_path: Path) -> None:
    request = _request(tmp_path)
    writer = SpyWriter(expected_final_mdl=request.output_mdl_path)

    result = export_retarget_preview_override(request, writer=writer)

    assert result.mdl_path == request.output_mdl_path
    assert result.mdx_path == request.output_mdx_path
    assert request.output_mdl_path.read_bytes() == b"out mdl"
    assert request.output_mdx_path.read_bytes() == b"out mdx"
    assert result.export_job_result is not None
    assert result.export_job_result.kind == "retarget_mdl_mdx"


def test_game_library_target_bytes_are_staged_as_original_mdl_source(tmp_path: Path) -> None:
    target = KotorModel(
        name="pmbam",
        root_node=ModelNode(name="root"),
        animations=[Animation(name="pause1", length=1.0)],
    )
    target._gr_source_mdl_bytes = b"game library mdl"
    target._gr_source_mdx_bytes = b"game library mdx"
    target._gr_source_resref = "pmbam"
    request = _request(tmp_path, target=target)
    writer = SpyWriter(
        expected_source_mdl_bytes=b"game library mdl",
        expected_source_mdx_bytes=b"game library mdx",
        expected_final_mdl=request.output_mdl_path,
    )

    result = export_retarget_preview_override(request, writer=writer)

    assert result.mdl_path == request.output_mdl_path
    assert request.output_mdl_path.read_bytes() == b"out mdl"
    assert not (request.output_mdl_path.parent / "_original_target").exists()


def test_original_target_model_is_not_mutated(tmp_path: Path) -> None:
    target = _target(tmp_path)
    before = copy.deepcopy(target)
    writer = SpyWriter(mutate_model=True)

    export_retarget_preview_override(_request(tmp_path, target=target), writer=writer)

    assert [anim.name for anim in target.animations] == [anim.name for anim in before.animations]
    assert [node.position for node in target.all_nodes()] == [node.position for node in before.all_nodes()]


def test_overwrite_false_blocks_existing_files_before_writer(tmp_path: Path) -> None:
    request = _request(tmp_path, overwrite=False)
    request.output_mdl_path.parent.mkdir(parents=True)
    request.output_mdl_path.write_bytes(b"existing")
    request.output_mdx_path.write_bytes(b"existing")
    writer = SpyWriter()

    with pytest.raises(RetargetPreviewExportError, match="overwrite existing"):
        export_retarget_preview_override(request, writer=writer)

    assert writer.calls == []


def test_basename_mismatch_warns_but_exports(tmp_path: Path) -> None:
    request = _request(tmp_path)
    request.output_mdl_path = tmp_path / "out" / "custom_name.mdl"
    request.output_mdx_path = request.output_mdl_path.with_suffix(".mdx")
    writer = SpyWriter()

    result = export_retarget_preview_override(request, writer=writer)

    assert result.mdl_path.name == "custom_name.mdl"
    assert any("filename to match the target model resref" in warning for warning in result.warnings)


def test_roundtrip_failure_is_reported_and_outputs_removed(tmp_path: Path) -> None:
    request = _request(tmp_path)
    writer = SpyWriter(success=False)

    with pytest.raises(RetargetPreviewExportError, match="readback verification"):
        export_retarget_preview_override(request, writer=writer)

    assert not request.output_mdl_path.exists()
    assert not request.output_mdx_path.exists()
    assert not request.output_mdl_path.with_suffix(".retarget_preview.json").exists()
