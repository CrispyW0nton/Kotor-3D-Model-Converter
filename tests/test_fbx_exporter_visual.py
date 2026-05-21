import json
from pathlib import Path

import pytest

from src.core.retargeting.fbx_exporter import (
    BLENDER_SCRIPT,
    _run_blender,
    export_day45_pmbam_g1a1,
    find_blender_executable,
)


@pytest.fixture(scope="module")
def day45_v6_export():
    out_dir = Path(".pytest_tmp_day45v6") / "day45_v6"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = export_day45_pmbam_g1a1(
        out_dir / "pmbam__g1a1__day4_5_v6.fbx",
        run_roundtrip_validation=True,
    )
    visual_path = Path(manifest.fbx_path).with_suffix(".visual.json")
    cmd = [
        str(find_blender_executable()),
        "--background",
        "--factory-startup",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--visual-validate",
        str(manifest.fbx_path),
        "--reference-intermediate",
        str(manifest.intermediate_path),
        "--visual-output",
        str(visual_path),
    ]
    result = _run_blender(cmd, timeout=300)
    assert result.returncode == 0, result.stderr
    return manifest, json.loads(visual_path.read_text(encoding="utf-8"))


def test_rest_pose_bbox_matches_aurora_native(day45_v6_export):
    _manifest, visual = day45_v6_export
    assert visual["height_ratio"] >= 0.99
    assert visual["width_ratio"] >= 0.99


def test_rest_pose_silhouette_matches_aurora(day45_v6_export):
    _manifest, visual = day45_v6_export
    assert visual["silhouette_ssim_proxy"] >= 0.95


def test_no_missing_arm_vertices(day45_v6_export):
    _manifest, visual = day45_v6_export
    ratios = visual["region_count_ratios"]
    assert ratios["left_arm"] >= 0.99
    assert ratios["right_arm"] >= 0.99


def test_animation_evaluates_without_explosion(day45_v6_export):
    _manifest, visual = day45_v6_export
    assert visual["max_center_distance_ratio"] < 2.0


def test_fbx_bindpose_valid(day45_v6_export):
    _manifest, visual = day45_v6_export
    validity = visual["bind_pose_validity"]
    assert validity["bind_pose_present"] is True
    assert validity["all_influencing_bones_present"] is True
    assert validity["all_parent_bones_present"] is True


def test_unity_humanoid_required_bones_present(day45_v6_export):
    _manifest, visual = day45_v6_export
    assert visual["required_unity_humanoid_missing"] == []
