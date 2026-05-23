"""KOTOR-to-Unreal ExportJob/FBX backend contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from src.core.retargeting.kotor_source_animation import KotorAnimationSourceReport
from src.core.retargeting.source_animation import Transform
from src.core.retargeting.ue_fbx_exporter import (
    KotorToUnrealExportRequest,
    export_kotor_to_unreal_preview,
)
from src.core.retargeting.unreal_target_skeleton import (
    UnrealAnimationClip,
    UnrealAnimationPose,
    UnrealSkeletonNode,
    UnrealTargetSkeleton,
)
from src.core.validation.validation_bus import ValidationReport


class FakeFbxBackend:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available
        self.calls: list[Path] = []

    def is_available(self) -> bool:
        return self.available

    def export_animation_clip(self, *, target_skeleton, animation_clip, output_fbx_path: Path, metadata=None) -> None:
        self.calls.append(Path(output_fbx_path))
        Path(output_fbx_path).write_bytes(
            f"FBX:{target_skeleton.name}:{animation_clip.clip_name}".encode("utf-8")
        )


def _preview_result() -> SimpleNamespace:
    skeleton = UnrealTargetSkeleton(
        name="UE5 Manny",
        nodes=[UnrealSkeletonNode("root", None, 0, Transform(), Transform(), "root")],
    )
    clip = UnrealAnimationClip(
        clip_name="pmbam_pause1",
        duration_seconds=1.0,
        sample_rate=30.0,
        target_skeleton_name=skeleton.name,
        poses=[
            UnrealAnimationPose(
                time_seconds=0.0,
                local_transforms={"root": Transform()},
                global_transforms={"root": Transform()},
            )
        ],
        metadata={"root_motion_policy": "in_place", "basis_conversion": "identity"},
    )
    sample_result = SimpleNamespace(
        report=KotorAnimationSourceReport("pmbam", "pause1", None, 1.0, 2, 1, 1, False)
    )
    return SimpleNamespace(
        source_sample_result=sample_result,
        target_skeleton=skeleton,
        animation_clip=clip,
        validation_report=ValidationReport(source="test"),
        metadata={"source_kotor_animation": "pause1"},
    )


def test_missing_fbx_backend_fails_before_writing(tmp_path: Path) -> None:
    output = tmp_path / "pmbam_pause1.fbx"

    result = export_kotor_to_unreal_preview(
        KotorToUnrealExportRequest(
            preview_result=_preview_result(),
            output_fbx_path=output,
            exporter_backend=None,
        )
    )

    assert result.succeeded is False
    assert not output.exists()
    assert not output.with_suffix(".ghostrigger.json").exists()
    assert "FBX export backend" in result.validation_report.issues[0].message


def test_fake_backend_exports_through_export_job(tmp_path: Path) -> None:
    output = tmp_path / "pmbam_pause1.fbx"
    backend = FakeFbxBackend()

    result = export_kotor_to_unreal_preview(
        KotorToUnrealExportRequest(
            preview_result=_preview_result(),
            output_fbx_path=output,
            exporter_backend=backend,
        )
    )

    assert result.succeeded is True
    assert output.exists()
    assert output.read_bytes().startswith(b"FBX:UE5 Manny:pmbam_pause1")
    assert output.with_suffix(".ghostrigger.json").exists()
    assert backend.calls and ".ghostrigger_export_" in str(backend.calls[0])


def test_export_manifest_includes_source_target_output_metadata(tmp_path: Path) -> None:
    output = tmp_path / "pmbam_pause1.fbx"
    result = export_kotor_to_unreal_preview(
        KotorToUnrealExportRequest(
            preview_result=_preview_result(),
            output_fbx_path=output,
            exporter_backend=FakeFbxBackend(),
        )
    )

    manifest = json.loads(output.with_suffix(".ghostrigger.json").read_text(encoding="utf-8"))

    assert result.succeeded is True
    assert manifest["mode"] == "kotor_to_unreal"
    assert manifest["source_kotor_animation"] == "pause1"
    assert manifest["output_unreal_clip_name"] == "pmbam_pause1"
    assert manifest["target_skeleton"] == "UE5 Manny"
    assert manifest["sample_rate"] == 30.0
