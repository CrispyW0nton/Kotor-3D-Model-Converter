import json
from pathlib import Path

import pytest

from src.core.retargeting.fbx_exporter import (
    blender_version,
    build_day4_pmbam_g1a1_asset,
    build_intermediate_representation,
    export_day4_pmbam_g1a1,
    find_blender_executable,
)


WORKSPACE_TMP = Path(".pytest_tmp_fbx_exporter")


def test_blender_installation_detected():
    blender = find_blender_executable()
    assert blender.exists()
    assert blender_version(blender).startswith("Blender 4.2.")


def test_intermediate_representation_deterministic():
    WORKSPACE_TMP.mkdir(exist_ok=True)
    rebound_a, baked_a, aligned_a, options_a = build_day4_pmbam_g1a1_asset(
        WORKSPACE_TMP / "deterministic.fbx",
        run_roundtrip_validation=False,
    )
    rebound_b, baked_b, aligned_b, options_b = build_day4_pmbam_g1a1_asset(
        WORKSPACE_TMP / "deterministic.fbx",
        run_roundtrip_validation=False,
    )
    first = build_intermediate_representation(rebound_a, baked_a, aligned_a, options_a)
    second = build_intermediate_representation(rebound_b, baked_b, aligned_b, options_b)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


@pytest.fixture(scope="module")
def day4_export():
    out_dir = WORKSPACE_TMP / "day4_fbx_export"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = export_day4_pmbam_g1a1(out_dir / "pmbam__g1a1__to__quinn_aligned.fbx")
    intermediate = json.loads(Path(manifest.intermediate_path).read_text(encoding="utf-8"))
    roundtrip = json.loads(Path(manifest.roundtrip_metrics["validation_path"]).read_text(encoding="utf-8"))
    return manifest, intermediate, roundtrip


def test_fbx_export_produces_file(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert Path(manifest.fbx_path).exists()
    assert Path(manifest.fbx_path).stat().st_size > 0


def test_fbx_manifest_written(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    manifest_path = Path(manifest.manifest_path)
    assert manifest_path.exists()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0"
    assert len(data["fbx_sha256"]) == 64


def test_fbx_roundtrip_bone_count(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["bone_count_expected"] == 89
    assert manifest.roundtrip_metrics["bone_count_match"] is True


def test_fbx_roundtrip_vertex_count(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["vertex_count_expected"] == 661
    assert manifest.roundtrip_metrics["vertex_count_match"] is True


def test_fbx_roundtrip_animation_frames(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["frame_count_expected"] == 89
    assert manifest.roundtrip_metrics["frame_count_match"] is True


def test_fbx_axis_system_declared_correctly(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["axis_system_observed"] == {
        "axis_up": "Z",
        "axis_forward": "-Y",
    }
    assert manifest.roundtrip_metrics["axis_system_match"] is True


def test_fbx_no_leaf_bones_added(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["no_leaf_bones_added"] is True
    assert manifest.roundtrip_metrics["leaf_bones"] == []


def test_fbx_rotation_fidelity_frame_zero(day4_export):
    manifest, _intermediate, _roundtrip = day4_export
    assert manifest.roundtrip_metrics["frame0_rotation_max_delta"] <= 1e-4
