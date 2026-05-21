from pathlib import Path

from src.core.retargeting.fbx_exporter import ClipManifestEntry, FBXExportManifest, compute_sha256
from src.workbench import ue5_rig_export
from src.workbench.ue5_rig_export import UE5RigExportRequest, export_ue5_rig


TEST_OUT = Path(".pytest_tmp_ue5_rig_export")


def _fake_export_manifest(fbx_path: Path) -> FBXExportManifest:
    fbx_path.parent.mkdir(parents=True, exist_ok=True)
    fbx_path.write_bytes(b"fake fbx payload")
    intermediate_path = fbx_path.with_name(f"{fbx_path.stem}_intermediate.json")
    intermediate_path.write_text("{}", encoding="utf-8")
    return FBXExportManifest(
        fbx_path=fbx_path,
        fbx_version="FBX201600",
        fbx_sha256=compute_sha256(fbx_path),
        blender_version="Blender 4.2.0",
        export_timestamp="2026-05-21T00:00:00Z",
        source_mesh_resref="pmbam",
        source_skeleton_id="kotor_pmbam",
        aligned_skeleton_id="kotor_pmbam_renamed_ue5_native_pose",
        bone_map_version="rename-map-sha",
        clip_inventory=[
            ClipManifestEntry(
                clip_name="g1a1",
                source_supermodel="S_Male02",
                frame_count=45,
                fps=30.0,
                duration_seconds=1.4667,
                sampling_strategy="fixed_30fps_delta_from_rest",
            )
        ],
        bind_pose_validation={
            "aurora_bone_count": 58.0,
            "twist_leaf_count": 8.0,
            "helper_leaf_count": 2.0,
            "weight_conservation_max_drift": 0.0,
        },
        axis_system={"axis_up": "Z", "axis_forward": "-Y"},
        roundtrip_metrics={
            "bone_count_expected": 68,
            "bone_count_observed": 68,
            "bone_count_match": True,
            "vertex_count_expected": 1184,
            "vertex_count_observed": 1184,
            "vertex_count_match": True,
            "frame_count_expected": 45,
            "frame_count_observed": 45,
            "frame_count_match": True,
            "axis_system_match": True,
            "no_leaf_bones_added": True,
        },
        intermediate_path=intermediate_path,
        manifest_path=fbx_path.with_suffix(".manifest.json"),
        schema_version="4.0.0-day4_5_v6",
    )


def _passing_visual(path: Path) -> dict:
    visual = {
        "height_ratio": 1.0,
        "width_ratio": 1.0,
        "silhouette_ssim_proxy": 0.999,
        "required_unity_humanoid_missing": [],
        "bind_pose_validity": {
            "bind_pose_present": True,
            "all_influencing_bones_present": True,
            "all_parent_bones_present": True,
        },
    }
    path.write_text("{}\n", encoding="utf-8")
    return visual


def _patch_success(monkeypatch):
    monkeypatch.setattr(
        ue5_rig_export,
        "_run_v6_export",
        lambda fbx_path, character, animation: _fake_export_manifest(Path(fbx_path)),
    )
    monkeypatch.setattr(
        ue5_rig_export,
        "_run_visual_validation",
        lambda _manifest, visual_path: _passing_visual(Path(visual_path)),
    )


def test_export_request_validates_character_exists():
    result = export_ue5_rig(UE5RigExportRequest("unknown", "g1a1", TEST_OUT / "bad_character"))
    assert result.success is False
    assert "character" in (result.halt_reason or "").lower()


def test_export_request_validates_animation_exists():
    result = export_ue5_rig(UE5RigExportRequest("pmbam", "missing", TEST_OUT / "bad_animation"))
    assert result.success is False
    assert "animation" in (result.halt_reason or "").lower()


def test_successful_export_produces_all_artifacts(monkeypatch):
    _patch_success(monkeypatch)
    result = export_ue5_rig(UE5RigExportRequest("pmbam", "g1a1", TEST_OUT / "success"))
    assert result.success is True
    assert result.fbx_path and result.fbx_path.exists()
    assert result.manifest_path and result.manifest_path.exists()
    assert result.visual_gate_path and result.visual_gate_path.exists()
    assert result.ue5_setup_notes_path and result.ue5_setup_notes_path.exists()
    assert result.fbx_sha256 == compute_sha256(result.fbx_path)


def test_manifest_schema_valid(monkeypatch):
    _patch_success(monkeypatch)
    result = export_ue5_rig(UE5RigExportRequest("pmbam", "g1a1", TEST_OUT / "manifest"))
    manifest = result.manifest_path.read_text(encoding="utf-8")
    assert '"pipeline_version": "day4_5_v6"' in manifest
    assert '"character_name": "pmbam"' in manifest
    assert '"all_gates_passed": true' in manifest
    assert '"all_19_humanoid_bones_present": true' in manifest


def test_ue5_setup_notes_contains_character_specifics(monkeypatch):
    _patch_success(monkeypatch)
    result = export_ue5_rig(UE5RigExportRequest("pmbam", "g1a1", TEST_OUT / "notes"))
    notes = result.ue5_setup_notes_path.read_text(encoding="utf-8")
    assert "UE5 Setup Notes - pmbam" in notes
    assert "g1a1" in notes
    assert "IK Retargeter Setup" in notes


def test_halt_on_validation_failure_returns_reason(monkeypatch):
    monkeypatch.setattr(
        ue5_rig_export,
        "_run_v6_export",
        lambda fbx_path, character, animation: _fake_export_manifest(Path(fbx_path)),
    )
    monkeypatch.setattr(
        ue5_rig_export,
        "_run_visual_validation",
        lambda _manifest, _visual_path: {
            "height_ratio": 0.5,
            "width_ratio": 1.0,
            "silhouette_ssim_proxy": 0.99,
            "required_unity_humanoid_missing": [],
            "bind_pose_validity": {
                "bind_pose_present": True,
                "all_influencing_bones_present": True,
                "all_parent_bones_present": True,
            },
        },
    )
    result = export_ue5_rig(UE5RigExportRequest("pmbam", "g1a1", TEST_OUT / "halt"))
    assert result.success is False
    assert "height ratio" in (result.halt_reason or "")
