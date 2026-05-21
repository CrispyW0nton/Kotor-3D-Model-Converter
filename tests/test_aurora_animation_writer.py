"""Tests for Sprint 3 R3.B Aurora animation injection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.game.kotor_loader import load_model_from_file
from src.core.retargeting.aurora_animation_writer import (
    CTRL_ORIENTATION,
    CTRL_POSITION,
    AuroraAnimationInjectionRequest,
    AuroraAnimationWriter,
)


TARGET_MDL = Path("tests/fixtures/kotor_stock/k1/pmbam.mdl")


def _write_synthetic_r3a(path: Path) -> None:
    frames = [
        {
            "frame": 1,
            "time_seconds": 0.0,
            "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
            "location_xyz": [0.0, 0.0, 0.0],
        },
        {
            "frame": 2,
            "time_seconds": 1.0 / 30.0,
            "rotation_wxyz": [0.999, 0.0, 0.0447, 0.0],
            "location_xyz": [0.0, 0.0, 0.0],
        },
    ]
    payload = {
        "schema": "sprint3_r3a_retarget_ready_animation",
        "frame_count": 2,
        "fps": 30.0,
        "duration_seconds": 2.0 / 30.0,
        "target_slot": "victory",
        "target_curves": {
            "rootdummy": {
                "target_bone": "rootdummy",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
            "pelvis_g": {
                "target_bone": "pelvis_g",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
            "torso_g": {
                "target_bone": "torso_g",
                "source_rest_world": {"rotation_wxyz": [1.0, 0.0, 0.0, 0.0]},
                "frames": frames,
            },
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_request_requires_existing_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        AuroraAnimationInjectionRequest(
            r3a_animation_json=tmp_path / "missing.json",
            target_mdl=tmp_path / "missing.mdl",
            animation_slot="victory",
            output_mdl=tmp_path / "out.mdl",
            output_manifest=tmp_path / "manifest.json",
        )


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_build_animation_from_r3a_creates_aurora_controllers(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))

    warnings: list[str] = []
    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=True,
        warnings=warnings,
    )

    assert animation.name == "victory"
    assert animation.anim_root == "PMBAM"
    assert len(animation.nodes) == 3
    first = animation.nodes[0]
    assert {ctrl["type"] for ctrl in first.controllers} == {CTRL_POSITION, CTRL_ORIENTATION}
    orientation = next(ctrl for ctrl in first.controllers if ctrl["type"] == CTRL_ORIENTATION)
    assert orientation["columns"] == 4
    assert len(orientation["times"]) == 2
    assert len(orientation["values"][0]) == 4
    assert warnings


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_rest_relative_identity_delta_preserves_target_bind_rotation(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    pelvis_anim = next(node for node in animation.nodes if node.name.lower() == "pelvis_g")
    orientation = next(ctrl for ctrl in pelvis_anim.controllers if ctrl["type"] == CTRL_ORIENTATION)
    assert orientation["values"][0] == pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_clip_frame_zero_is_retarget_reference_pose(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    model = load_model_from_file(str(TARGET_MDL), str(TARGET_MDL.with_suffix(".mdx")))
    payload = json.loads(r3a.read_text(encoding="utf-8"))
    payload["target_curves"]["pelvis_g"]["source_rest_world"]["rotation_wxyz"] = [1.0, 0.0, 0.0, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][0]["rotation_wxyz"] = [0.9238795, 0.0, 0.3826834, 0.0]
    payload["target_curves"]["pelvis_g"]["frames"][1]["rotation_wxyz"] = [0.9063078, 0.0, 0.4226183, 0.0]

    animation = AuroraAnimationWriter().build_animation_from_r3a(
        payload=payload,
        model=model,
        slot_name="victory",
        write_zero_position_controllers=False,
    )

    pelvis_anim = next(node for node in animation.nodes if node.name.lower() == "pelvis_g")
    orientation = next(ctrl for ctrl in pelvis_anim.controllers if ctrl["type"] == CTRL_ORIENTATION)
    assert orientation["values"][0] == pytest.approx(list(model.find_node("pelvis_g").rotation), abs=1e-6)


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_inject_writes_binary_mdl_and_mdx(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    output_mdl = tmp_path / "pmbam__victory__r3b.mdl"
    manifest = tmp_path / "manifest.json"

    result = AuroraAnimationWriter().inject(
        AuroraAnimationInjectionRequest(
            r3a_animation_json=r3a,
            target_mdl=TARGET_MDL,
            animation_slot="victory",
            output_mdl=output_mdl,
            output_manifest=manifest,
        )
    )

    assert result.success, result.errors
    assert output_mdl.exists()
    assert output_mdl.with_suffix(".mdx").exists()
    assert manifest.exists()
    assert result.operation == "appended_local_override"
    assert result.output_size_bytes <= result.input_size_bytes * 2.0


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM fixture unavailable")
def test_injected_mdl_reloads_with_local_victory(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    _write_synthetic_r3a(r3a)
    output_mdl = tmp_path / "pmbam__victory__r3b.mdl"

    result = AuroraAnimationWriter().inject(
        AuroraAnimationInjectionRequest(
            r3a_animation_json=r3a,
            target_mdl=TARGET_MDL,
            animation_slot="victory",
            output_mdl=output_mdl,
            output_manifest=tmp_path / "manifest.json",
        )
    )

    assert result.success, result.errors
    reloaded = load_model_from_file(str(output_mdl), str(output_mdl.with_suffix(".mdx")))
    assert reloaded is not None
    assert any(anim.name.lower() == "victory" for anim in reloaded.animations)


def test_result_manifest_is_json_serializable(tmp_path: Path):
    r3a = tmp_path / "r3a.json"
    target = tmp_path / "target.mdl"
    r3a.write_text("{}", encoding="utf-8")
    target.write_bytes(b"dummy")

    request = AuroraAnimationInjectionRequest(
        r3a_animation_json=r3a,
        target_mdl=target,
        animation_slot="victory",
        output_mdl=tmp_path / "out.mdl",
        output_manifest=tmp_path / "manifest.json",
    )
    result = AuroraAnimationWriter()._finish(
        result=__import__(
            "src.core.retargeting.aurora_animation_writer",
            fromlist=["AuroraAnimationInjectionResult"],
        ).AuroraAnimationInjectionResult(success=False, animation_slot="victory"),
        request=request,
    )

    assert result.success is False
    payload = json.loads(request.output_manifest.read_text(encoding="utf-8"))
    assert payload["animation_slot"] == "victory"
