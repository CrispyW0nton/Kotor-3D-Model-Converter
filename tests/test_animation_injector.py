"""Tests for Sprint 3 R3.A reverse animation extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.retargeting.animation_injector import (
    AnimationInjectionRequest,
    AnimationInjectionResult,
    AnimationInjector,
)
from src.core.retargeting.reverse_renamer import load_reverse_rename_spec
from src.core.retargeting.ue5_source_adapter import UE5SourceAdapter


SOURCE_FBX = Path(
    r"C:\Users\NewAdmin\Documents\KaiGenInteractive\AnimationLibrary\Exports\M_Neutral_Stand_Idle_Loop_export.fbx"
)
TARGET_MDL = Path("tests/fixtures/kotor_stock/k1/pmbam.mdl")
RENAME_MAP = Path("knowledge_base/retargeting/ue5_to_aurora_rename_map.json")


def test_request_validation_requires_existing_files(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        AnimationInjectionRequest(
            source_fbx=Path("missing.fbx"),
            target_mdl=Path("missing.mdl"),
            target_slot="victory",
            rename_map_path=Path("missing.json"),
            output_dir=tmp_path,
        )


def test_result_serialization():
    result = AnimationInjectionResult(
        success=True,
        source_fbx=Path("source.fbx"),
        target_mdl_original=Path("pmbam.mdl"),
        target_slot="victory",
    )

    payload = result.to_dict()

    assert payload["success"] is True
    assert payload["phase"] == "R3A_EXTRACT_ONLY"
    assert payload["target_slot"] == "victory"


def test_ue5_source_adapter_maps_core_and_aliases():
    spec = load_reverse_rename_spec(RENAME_MAP)
    target_bones = list(spec.rename_pairs.values())
    source_bones = ["attach", "pelvis", "spine_01", "upperarm_l", "lowerarm_l", "hand_l"]

    result = UE5SourceAdapter().adapt(source_bones, spec, target_bones)

    assert result.target_for("attach") == "rootdummy"
    assert result.target_for("pelvis") == "pelvis_g"
    assert result.target_for("hand_l") == "lhand_g"
    assert not result.unmapped


def test_ue5_source_adapter_drops_expected_helpers():
    spec = load_reverse_rename_spec(RENAME_MAP)
    source_bones = [
        "ik_foot_root",
        "lowerarm_twist_01_l",
        "index_01_l",
        "weapon_l",
        "spine_02",
    ]

    result = UE5SourceAdapter().adapt(source_bones, spec)

    assert {item.source_bone for item in result.dropped} >= {
        "ik_foot_root",
        "lowerarm_twist_01_l",
        "index_01_l",
        "weapon_l",
    }
    assert {item.source_bone for item in result.collapsed} == {"spine_02"}


def _fake_extraction_payload(spec):
    source_bones = sorted(spec.rename_pairs)
    curves = {
        source: [
            {
                "frame": 0,
                "time_seconds": 0.0,
                "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
                "location_xyz": [0.0, 0.0, 0.0],
                "matrix": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
            }
        ]
        for source in source_bones
    }
    return {
        "success": True,
        "source_bone_count": len(source_bones),
        "source_bones": source_bones,
        "bone_parents": {source: None for source in source_bones},
        "rest_world": {
            source: {
                "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
                "location_xyz": [0.0, 0.0, 0.0],
            }
            for source in source_bones
        },
        "rest_pose_bases": {
            source: {
                "world_matrix_at_rest": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "data_bone_matrix": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "head": [0.0, 0.0, 0.0],
                "tail": [0.0, 1.0, 0.0],
                "rotation_wxyz": [1.0, 0.0, 0.0, 0.0],
                "location_xyz": [0.0, 0.0, 0.0],
            }
            for source in source_bones
        },
        "action_name": "fake_idle",
        "frame_start": 0,
        "frame_end": 0,
        "frame_count": 1,
        "fps": 30.0,
        "curves": curves,
        "log_path": "",
    }


@pytest.mark.skipif(not TARGET_MDL.exists(), reason="PMBAM target fixture unavailable")
def test_extract_for_injection_writes_retargeted_json(tmp_path: Path, monkeypatch):
    spec = load_reverse_rename_spec(RENAME_MAP)
    source_fbx = tmp_path / "source.fbx"
    source_fbx.write_bytes(b"fake fbx")

    def fake_extract(**_kwargs):
        return _fake_extraction_payload(spec)

    monkeypatch.setattr(
        "src.core.retargeting.animation_injector.run_blender_animation_extraction",
        fake_extract,
    )

    request = AnimationInjectionRequest(
        source_fbx=source_fbx,
        target_mdl=TARGET_MDL,
        target_slot="victory",
        rename_map_path=RENAME_MAP,
        output_dir=tmp_path / "out",
    )
    result = AnimationInjector().inject(request)

    assert result.success, result.errors
    assert result.mapped_bone_count >= 19
    assert result.retargeted_animation_json is not None
    payload = json.loads(result.retargeted_animation_json.read_text(encoding="utf-8"))
    assert payload["schema"] == "sprint3_r3a_retarget_ready_animation"
    assert "pelvis_g" in payload["target_curves"]
    assert "source_rest_pose_bases" in payload
    assert payload["target_curves"]["pelvis_g"]["source_rest_basis"]["tail"] == [0.0, 1.0, 0.0]


@pytest.mark.skipif(
    not SOURCE_FBX.exists() or not TARGET_MDL.exists(),
    reason="External UE5 FBX or PMBAM target unavailable",
)
@pytest.mark.skipif(
    not bool(__import__("os").environ.get("GHOSTRIGGER_RUN_EXTERNAL_FBX_TESTS")),
    reason="Set GHOSTRIGGER_RUN_EXTERNAL_FBX_TESTS=1 to run Blender extraction",
)
def test_extract_real_idle_fbx_smoke(tmp_path: Path):
    request = AnimationInjectionRequest(
        source_fbx=SOURCE_FBX,
        target_mdl=TARGET_MDL,
        target_slot="victory",
        rename_map_path=RENAME_MAP,
        output_dir=tmp_path / "out",
    )
    result = AnimationInjector().inject(request)

    assert result.success, result.errors
    assert result.source_bone_count >= 80
    assert result.frame_count >= 300
    assert result.mapped_bone_count >= 19
