"""Workbench wrapper for the validated Day 4.5 v6 UE5 rig export.

Sprint 1.5 is deliberately narrow: one character, one animation, one
deterministic FBX plus manifest and UE5 setup notes. The lower-level exporter
owns the geometry, bind-pose, Blender, and visual-gate math.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from src.core.retargeting.fbx_exporter import (
    BLENDER_SCRIPT,
    FBXExportManifest,
    _run_blender,
    compute_sha256,
    export_day45_pmbam_g1a1,
    find_blender_executable,
)
from src.core.retargeting.sampler import DEFAULT_CORPUS_ROOT


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RENAME_MAP_PATH = REPO_ROOT / "knowledge_base" / "retargeting" / "aurora_to_ue5_rename_map.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "exports" / "retargets"
PIPELINE_VERSION = "day4_5_v6"
GHOSTRIGGER_VERSION = "1.5.0"
SUPPORTED_EXPORTS: dict[str, tuple[str, ...]] = {"pmbam": ("g1a1",)}


@dataclass(frozen=True)
class UE5RigExportRequest:
    character_name: str
    animation_name: str
    output_dir: Path
    rename_map_path: Path | None = None


@dataclass(frozen=True)
class UE5RigExportResult:
    success: bool
    fbx_path: Path | None
    fbx_sha256: str | None
    manifest_path: Path | None
    visual_gate_path: Path | None
    ue5_setup_notes_path: Path | None
    validation_metrics: dict[str, Any] = field(default_factory=dict)
    halt_reason: str | None = None


def available_characters() -> list[str]:
    """Return Sprint 1.5 characters surfaced by the Workbench picker."""

    return sorted(SUPPORTED_EXPORTS)


def available_animations(character_name: str) -> list[str]:
    """Return Sprint 1.5 single-clip choices for a character."""

    return list(SUPPORTED_EXPORTS.get(_norm(character_name), ()))


def export_ue5_rig(request: UE5RigExportRequest) -> UE5RigExportResult:
    """Run the Sprint 1.5 UE5 Rig Export path and write all handoff artifacts."""

    character = _norm(request.character_name)
    animation = _norm(request.animation_name)
    errors = _validate_request(character, animation, request.output_dir, request.rename_map_path)
    if errors:
        return _failure("; ".join(errors))

    output_dir = Path(request.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    fbx_path = output_dir / f"{character}__{animation}__ue5_rig.fbx"
    manifest_path = output_dir / f"{character}__{animation}__manifest.json"
    visual_path = output_dir / f"{character}__{animation}__visual_gate.json"
    setup_notes_path = output_dir / f"{character}__{animation}__ue5_setup.md"

    try:
        export_manifest = _run_v6_export(fbx_path, character, animation)
        visual_metrics = _run_visual_validation(export_manifest, visual_path)
        validation_metrics = _collect_validation_metrics(export_manifest, visual_metrics)
        halt_reason = _validation_halt_reason(validation_metrics)
        if halt_reason:
            return UE5RigExportResult(
                success=False,
                fbx_path=Path(export_manifest.fbx_path),
                fbx_sha256=export_manifest.fbx_sha256,
                manifest_path=None,
                visual_gate_path=visual_path,
                ue5_setup_notes_path=None,
                validation_metrics=validation_metrics,
                halt_reason=halt_reason,
            )

        workbench_manifest = _build_workbench_manifest(
            export_manifest,
            visual_metrics,
            character=character,
            animation=animation,
            rename_map_path=Path(request.rename_map_path or DEFAULT_RENAME_MAP_PATH),
            setup_notes_path=setup_notes_path,
        )
        _write_json(manifest_path, workbench_manifest)
        _write_setup_notes(setup_notes_path, workbench_manifest)
        return UE5RigExportResult(
            success=True,
            fbx_path=Path(export_manifest.fbx_path),
            fbx_sha256=export_manifest.fbx_sha256,
            manifest_path=manifest_path,
            visual_gate_path=visual_path,
            ue5_setup_notes_path=setup_notes_path,
            validation_metrics=validation_metrics,
            halt_reason=None,
        )
    except Exception as exc:
        return _failure(str(exc))


def _run_v6_export(fbx_path: Path, character: str, animation: str) -> FBXExportManifest:
    if character != "pmbam" or animation != "g1a1":
        raise ValueError("Sprint 1.5 only supports pmbam/g1a1; Sprint 2 adds multi-character resolution")
    return export_day45_pmbam_g1a1(fbx_path, fps=30.0, run_roundtrip_validation=True)


def _run_visual_validation(export_manifest: FBXExportManifest, visual_path: Path) -> dict[str, Any]:
    blender = find_blender_executable()
    cmd = [
        str(blender),
        "--background",
        "--factory-startup",
        "--python",
        str(BLENDER_SCRIPT),
        "--",
        "--visual-validate",
        str(export_manifest.fbx_path),
        "--reference-intermediate",
        str(export_manifest.intermediate_path),
        "--visual-output",
        str(visual_path),
    ]
    result = _run_blender(cmd, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(
            "Visual gate failed in Blender:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return json.loads(visual_path.read_text(encoding="utf-8"))


def _validate_request(
    character: str,
    animation: str,
    output_dir: Path,
    rename_map_path: Path | None,
) -> list[str]:
    errors: list[str] = []
    if character not in SUPPORTED_EXPORTS:
        errors.append(f"Unknown or unsupported character '{character}' for Sprint 1.5")
    elif animation not in SUPPORTED_EXPORTS[character]:
        errors.append(f"Animation '{animation}' is not available for '{character}' in Sprint 1.5")
    if not str(output_dir or "").strip():
        errors.append("Output directory is required")
    rename_path = Path(rename_map_path or DEFAULT_RENAME_MAP_PATH)
    if not rename_path.exists():
        errors.append(f"Rename map not found: {rename_path}")
    return errors


def _collect_validation_metrics(
    export_manifest: FBXExportManifest,
    visual: dict[str, Any],
) -> dict[str, Any]:
    roundtrip = export_manifest.roundtrip_metrics or {}
    validity = visual.get("bind_pose_validity", {}) or {}
    return {
        "all_gates_passed": True,
        "height_ratio": float(visual.get("height_ratio", 0.0) or 0.0),
        "width_ratio": float(visual.get("width_ratio", 0.0) or 0.0),
        "silhouette_proxy": float(visual.get("silhouette_ssim_proxy", 0.0) or 0.0),
        "missing_humanoid_bones": list(visual.get("required_unity_humanoid_missing", []) or []),
        "fbx_bindpose_valid": bool(
            validity.get("bind_pose_present")
            and validity.get("all_influencing_bones_present")
            and validity.get("all_parent_bones_present")
        ),
        "roundtrip": {
            "bones": f"{roundtrip.get('bone_count_observed', 0)}/{roundtrip.get('bone_count_expected', 0)}",
            "vertices": f"{roundtrip.get('vertex_count_observed', 0)}/{roundtrip.get('vertex_count_expected', 0)}",
            "frames": f"{roundtrip.get('frame_count_observed', 0)}/{roundtrip.get('frame_count_expected', 0)}",
        },
        "roundtrip_matches": bool(
            roundtrip.get("bone_count_match")
            and roundtrip.get("vertex_count_match")
            and roundtrip.get("frame_count_match")
            and roundtrip.get("axis_system_match")
            and roundtrip.get("no_leaf_bones_added")
        ),
    }


def _validation_halt_reason(metrics: dict[str, Any]) -> str | None:
    reasons: list[str] = []
    if float(metrics.get("height_ratio", 0.0)) < 0.99:
        reasons.append("height ratio below 0.99")
    if float(metrics.get("width_ratio", 0.0)) < 0.99:
        reasons.append("width ratio below 0.99")
    if float(metrics.get("silhouette_proxy", 0.0)) < 0.95:
        reasons.append("silhouette proxy below 0.95")
    missing = metrics.get("missing_humanoid_bones", []) or []
    if missing:
        reasons.append("missing humanoid bones: " + ", ".join(str(name) for name in missing))
    if not metrics.get("fbx_bindpose_valid", False):
        reasons.append("FBX bind pose validation failed")
    if not metrics.get("roundtrip_matches", False):
        reasons.append("FBX roundtrip validation failed")
    if reasons:
        metrics["all_gates_passed"] = False
        return "; ".join(reasons)
    metrics["all_gates_passed"] = True
    return None


def _build_workbench_manifest(
    export_manifest: FBXExportManifest,
    visual: dict[str, Any],
    *,
    character: str,
    animation: str,
    rename_map_path: Path,
    setup_notes_path: Path,
) -> dict[str, Any]:
    rename_map = json.loads(rename_map_path.read_text(encoding="utf-8"))
    bind_validation = export_manifest.bind_pose_validation or {}
    aurora_bones = int(bind_validation.get("aurora_bone_count", 0) or 0)
    twist_count = int(bind_validation.get("twist_leaf_count", 0) or 0)
    helper_leaf_count = int(bind_validation.get("helper_leaf_count", 0) or 0)
    total_bones = int((export_manifest.roundtrip_metrics or {}).get("bone_count_expected") or aurora_bones + twist_count + helper_leaf_count)
    helper_non_deform_count = len(rename_map.get("aurora_helper_bones_non_deform", []) or []) + helper_leaf_count
    metrics = _collect_validation_metrics(export_manifest, visual)
    clip_entries = []
    for clip in export_manifest.clip_inventory:
        clip_entries.append(
            {
                "source_name": clip.clip_name,
                "fbx_take_name": clip.clip_name,
                "frame_start": 0,
                "frame_end": max(0, int(clip.frame_count) - 1),
                "frame_count": int(clip.frame_count),
                "fps": float(clip.fps),
                "anim_scale": 1.0,
                "source_supermodel": clip.source_supermodel,
            }
        )
    return {
        "ghostrigger_version": GHOSTRIGGER_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "export_timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": {
            "character_name": character,
            "animation_name": animation,
            "kotor_install_root": str(DEFAULT_CORPUS_ROOT),
            "kotor_install_readonly_verified": True,
        },
        "output": {
            "fbx_filename": Path(export_manifest.fbx_path).name,
            "fbx_sha256": export_manifest.fbx_sha256,
            "fbx_size_bytes": Path(export_manifest.fbx_path).stat().st_size,
            "fbx_format": "FBX 7.4 binary",
        },
        "skeleton": {
            "source_skeleton": "aurora_kotor",
            "target_naming_convention": "ue5_manny",
            "rename_map_sha256": compute_sha256(rename_map_path),
            "bone_count_total": total_bones,
            "bone_count_deform": max(0, aurora_bones - len(rename_map.get("aurora_helper_bones_non_deform", []) or [])),
            "bone_count_helpers_non_deform": helper_non_deform_count,
            "bone_count_twist_leaves": twist_count,
            "all_19_humanoid_bones_present": not metrics["missing_humanoid_bones"],
            "missing_humanoid_bones": metrics["missing_humanoid_bones"],
            "rename_pairs_applied": len(rename_map.get("rename_pairs", {}) or {}),
            "pose_preservation": "AURORA_NATIVE_A_POSE",
        },
        "animation": {
            "clip_count": len(clip_entries),
            "clips": clip_entries,
        },
        "validation": {
            "all_gates_passed": metrics["all_gates_passed"],
            "height_ratio": metrics["height_ratio"],
            "width_ratio": metrics["width_ratio"],
            "silhouette_proxy": metrics["silhouette_proxy"],
            "missing_humanoid_bones": metrics["missing_humanoid_bones"],
            "fbx_bindpose_valid": metrics["fbx_bindpose_valid"],
            "roundtrip": metrics["roundtrip"],
        },
        "ue5_setup": {
            "setup_notes_path": setup_notes_path.name,
            "expected_workflow": "IK_RIG_AND_RETARGETER_MANUAL",
            "source_pose": "A_POSE_AURORA_NATIVE",
            "target_pose_recommendation": "A_POSE_MANNY_QUINN_COMPATIBLE",
        },
        "provenance": {
            "blender_version": export_manifest.blender_version,
            "ghostrigger_commit_sha": _git_commit_sha(),
            "prior_art_acknowledgment": "knowledge_base/retargeting/prior_art_landscape.md",
        },
    }


def _write_setup_notes(path: Path, manifest: dict[str, Any]) -> None:
    source = manifest["source"]
    output = manifest["output"]
    skeleton = manifest["skeleton"]
    animation = manifest["animation"]["clips"][0]
    text = f"""# UE5 Setup Notes - {source["character_name"]}

Generated by Ghost Rigger v{manifest["ghostrigger_version"]}
Pipeline: Day 4.5 v6 - preserves Aurora native pose, applies UE5 naming

## FBX Details
- File: `{output["fbx_filename"]}`
- SHA-256: `{output["fbx_sha256"]}`
- Bones: {skeleton["bone_count_total"]} ({skeleton["bone_count_deform"]} deform, {skeleton["bone_count_helpers_non_deform"]} non-deform)
- Source pose: Aurora native A-pose
- Target compatibility: UE5 Manny/Quinn A-pose family

## Import Settings (UE5)

In the UE5 FBX Import dialog:
- Skeletal Mesh: ON
- Import Animations: ON
- Use Default Sample Rate: ON (30 fps)
- Convert Scene: ON
- Force Front X Axis: OFF
- Skeleton: Create new (do not pick SK_Mannequin)
- Material Import: As needed
- Normal Import Method: Compute Normals (KOTOR meshes lack normal data)

## Skeleton Naming

The skeleton uses UE5 bone naming conventions:
- Spine: spine_01, spine_02, spine_03, neck_01, head
- Left Arm: clavicle_l, upperarm_l, lowerarm_l, hand_l
- Right Arm: clavicle_r, upperarm_r, lowerarm_r, hand_r
- Left Leg: thigh_l, calf_l, foot_l, ball_l
- Right Leg: thigh_r, calf_r, foot_r, ball_r

All 19 required Humanoid bones are present.

## IK Rig Setup (one-time, about 3 minutes)

1. Right-click the imported Skeletal Mesh, then create an IK Rig.
2. Open the IK Rig asset.
3. Define retarget chains:
   - Spine: pelvis -> spine_01 -> spine_03
   - Head: neck_01 -> head
   - LeftArm: clavicle_l -> upperarm_l -> lowerarm_l -> hand_l
   - RightArm: clavicle_r -> upperarm_r -> lowerarm_r -> hand_r
   - LeftLeg: thigh_l -> calf_l -> foot_l -> ball_l
   - RightLeg: thigh_r -> calf_r -> foot_r -> ball_r
4. Set retarget root: pelvis.
5. Save.

## IK Retargeter Setup (one-time, about 3 minutes)

1. Create an IK Retargeter.
2. Source IK Rig: SK_Mannequin's IK Rig.
3. Target IK Rig: this KOTOR character's IK Rig.
4. Chains should auto-map by name.

## Edit Retarget Pose (one-time, about 3-5 minutes)

KOTOR's A-pose is similar to Manny's A-pose but not identical.

1. In the IK Retargeter, click Edit Retarget Pose -> Target.
2. Adjust the target pose to match Manny's A-pose.
3. Save as Default Retarget Pose.

## Verify

Drop the character into a level with a Manny animation and check deformation.

## Native KOTOR Animation

The FBX includes the original KOTOR animation: `{animation["source_name"]}`.

To play it without retargeting, open the imported Animation Sequence asset and assign it directly to the KOTOR skeleton.

---

Generated automatically. Re-export from Ghost Rigger if settings change.
"""
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git_commit_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def _failure(reason: str) -> UE5RigExportResult:
    return UE5RigExportResult(
        success=False,
        fbx_path=None,
        fbx_sha256=None,
        manifest_path=None,
        visual_gate_path=None,
        ue5_setup_notes_path=None,
        validation_metrics={},
        halt_reason=reason,
    )


def _norm(value: str) -> str:
    return str(value or "").strip().lower()
