"""Sprint 3 Gate 2 validation for an exported UE5 Manny sample FBX.

This script consumes the Blender inspection JSON produced by
``scripts/blender_gate2_inspect_fbx.py`` and compares it against the PMBAM
Aurora bind-pose contract from Day 4.5 v6.  It intentionally writes plain JSON
and Markdown artifacts so the reverse-retargeting gate can be reviewed without
opening Blender again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.retargeting.apose_compatibility import validate_apose_compatibility
from src.core.retargeting.coordinate_normalizer import matrix_to_quat_wxyz
from src.core.retargeting.reverse_renamer import (
    load_reverse_rename_spec,
    validate_reverse_rename_spec,
)


HUMANOID_CORE = {
    "pelvis",
    "spine_01",
    "spine_03",
    "clavicle_l",
    "clavicle_r",
    "upperarm_l",
    "upperarm_r",
    "lowerarm_l",
    "lowerarm_r",
    "hand_l",
    "hand_r",
    "thigh_l",
    "thigh_r",
    "calf_l",
    "calf_r",
    "foot_l",
    "foot_r",
    "ball_l",
    "ball_r",
}

KNOWN_UE5_EXTRAS = {
    "attach",
    "global",
    "ik_foot_root",
    "ik_foot_l",
    "ik_foot_r",
    "ik_hand_root",
    "ik_hand_gun",
    "ik_hand_l",
    "ik_hand_r",
    "interaction",
    "center_of_mass",
    "weapon_l",
    "weapon_r",
    "camera",
}

FINGER_TOKENS = (
    "thumb_",
    "index_",
    "middle_",
    "ring_",
    "pinky_",
)


def _key(name: str) -> str:
    return str(name or "").strip().lower()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pmbam_world_rotations(contract: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    rotations: dict[str, tuple[float, float, float, float]] = {}
    for name, bone in contract.get("bones", {}).items():
        matrix = np.asarray(bone["bind_world_matrix_4x4"], dtype=np.float64)
        rotations[_key(name)] = tuple(float(v) for v in matrix_to_quat_wxyz(matrix))
    return rotations


def _sort_bone_deltas(report) -> list[dict[str, Any]]:
    return [
        {
            "source_bone": delta.source_bone,
            "target_bone": delta.target_bone,
            "angular_delta_degrees": delta.angular_delta_degrees,
            "within_15_degrees": delta.within_tolerance,
            "within_25_degrees": delta.angular_delta_degrees <= 25.0,
        }
        for delta in sorted(report.bone_deltas, key=lambda item: item.angular_delta_degrees, reverse=True)
    ]


def _unaccounted_source_bones(source_bones: set[str], spec) -> list[str]:
    mapped = set(spec.rename_pairs)
    dropped = set(spec.ue5_only_bones_dropped) | set(spec.synthetic_helper_bones_dropped)
    finger_bones = {name for name in source_bones if any(token in name for token in FINGER_TOKENS)}
    twist_bones = {name for name in source_bones if "twist" in name}
    return sorted(source_bones - mapped - dropped - KNOWN_UE5_EXTRAS - finger_bones - twist_bones)


def _gate_status(apose_report, reverse_errors: list[str], unaccounted_core: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    core_failures = [
        delta
        for delta in apose_report.bone_deltas
        if delta.source_bone in HUMANOID_CORE and delta.angular_delta_degrees > 25.0
    ]
    if core_failures:
        reasons.append(
            "A-pose delta exceeded 25 degrees on core bones: "
            + ", ".join(f"{d.source_bone}={d.angular_delta_degrees:.2f}" for d in core_failures)
        )
        return "HALT", reasons
    if apose_report.max_delta_degrees > 25.0:
        reasons.append(f"A-pose max delta exceeded 25 degrees: {apose_report.max_delta_degrees:.2f}")
        return "HALT", reasons
    if reverse_errors:
        reasons.append(f"Reverse rename validation has {len(reverse_errors)} structural issue(s)")
    if unaccounted_core:
        reasons.append("Core source bones not mapped or explicitly dropped: " + ", ".join(unaccounted_core))
    if apose_report.max_delta_degrees > apose_report.tolerance_degrees:
        reasons.append(
            f"A-pose max delta is marginal: {apose_report.max_delta_degrees:.2f} > "
            f"{apose_report.tolerance_degrees:.2f}"
        )
    return ("CONDITIONAL" if reasons else "PASS"), reasons


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    report = payload["apose_validation"]
    reverse = payload["reverse_rename_validation"]
    export = payload["exported_fbx"]
    lines = [
        "# Sprint 3 Gate 2 - UE5 Sample Reverse-Retarget Validation",
        "",
        f"Status: **{payload['status']}**",
        "",
        "## Exported FBX",
        "",
        f"- Path: `{export['path']}`",
        f"- SHA-256: `{export['sha256']}`",
        f"- Size: `{export['size_bytes']}` bytes",
        f"- Skeleton: `{payload['blender_inspection']['armature_name']}`",
        f"- Bones: `{payload['blender_inspection']['bone_count']}`",
        f"- Actions: `{payload['blender_inspection']['actions']}`",
        f"- Screenshot: `{payload['blender_inspection']['screenshot_path']}`",
        "",
        "## A-Pose Validation",
        "",
        f"- Compatible at 15 degrees: `{report['compatible']}`",
        f"- Max delta: `{report['max_delta_degrees']:.4f}` degrees",
        f"- Missing source bones: `{report['missing_source_bones']}`",
        f"- Missing target bones: `{report['missing_target_bones']}`",
        "",
        "Worst deltas:",
        "",
        "| Source | Target | Delta | Within 25 deg |",
        "|---|---|---:|---|",
    ]
    for delta in report["bone_deltas"][:10]:
        lines.append(
            f"| `{delta['source_bone']}` | `{delta['target_bone']}` | "
            f"{delta['angular_delta_degrees']:.4f} | `{delta['within_25_degrees']}` |"
        )
    lines.extend(
        [
            "",
            "## Reverse Rename Validation",
            "",
            f"- Structural errors: `{reverse['errors']}`",
            f"- Mapped source bones present: `{reverse['mapped_source_present_count']}`",
            f"- Missing mapped source bones: `{reverse['missing_mapped_source']}`",
            f"- Missing mapped target bones: `{reverse['missing_mapped_target']}`",
            f"- Unaccounted source bones after known extras/fingers/twists: `{reverse['unaccounted_source_bones']}`",
            f"- Unaccounted core bones: `{reverse['unaccounted_core_bones']}`",
            "",
            "## Decision Notes",
            "",
        ]
    )
    for reason in payload["status_reasons"] or ["All Gate 2 checks passed."]:
        lines.append(f"- {reason}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fbx", required=True, type=Path)
    parser.add_argument("--inspect-json", required=True, type=Path)
    parser.add_argument("--pmbam-contract", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()

    inspect = _load_json(args.inspect_json)
    pmbam = _load_json(args.pmbam_contract)
    spec = load_reverse_rename_spec()

    source_bones = {_key(name) for name in inspect["bone_names"]}
    target_bones = {_key(name) for name in pmbam["bones"]}
    source_rotations = {
        _key(name): tuple(float(v) for v in quat)
        for name, quat in inspect["rest_world_rotations_wxyz"].items()
    }
    target_rotations = _pmbam_world_rotations(pmbam)

    apose_report = validate_apose_compatibility(
        source_rotations,
        target_rotations,
        spec.rename_pairs,
        tolerance_degrees=15.0,
    )
    reverse_errors = validate_reverse_rename_spec(
        spec,
        source_bones,
        target_bones,
        require_all_source_bones_accounted=False,
    )

    missing_mapped_source = sorted(set(spec.rename_pairs) - source_bones)
    missing_mapped_target = sorted({_key(name) for name in spec.rename_pairs.values()} - target_bones)
    unaccounted = _unaccounted_source_bones(source_bones, spec)
    unaccounted_core = sorted(HUMANOID_CORE & set(unaccounted))
    status, reasons = _gate_status(apose_report, reverse_errors, unaccounted_core)

    payload = {
        "status": status,
        "status_reasons": reasons,
        "exported_fbx": {
            "path": str(args.fbx),
            "sha256": _sha256(args.fbx),
            "size_bytes": args.fbx.stat().st_size,
        },
        "blender_inspection": {
            "json_path": str(args.inspect_json),
            "screenshot_path": inspect.get("screenshot_path"),
            "armature_name": inspect.get("armature_name"),
            "bone_count": inspect.get("bone_count"),
            "mesh_count": inspect.get("mesh_count"),
            "frame_start": inspect.get("frame_start"),
            "frame_end": inspect.get("frame_end"),
            "frame_count": inspect.get("frame_count"),
            "fps": inspect.get("fps"),
            "actions": inspect.get("actions", []),
            "bbox": inspect.get("bbox"),
        },
        "apose_validation": {
            "compatible": apose_report.compatible,
            "tolerance_degrees": apose_report.tolerance_degrees,
            "max_delta_degrees": apose_report.max_delta_degrees,
            "missing_source_bones": apose_report.missing_source_bones,
            "missing_target_bones": apose_report.missing_target_bones,
            "failed_bones_15_degrees": [
                delta.source_bone for delta in apose_report.bone_deltas if not delta.within_tolerance
            ],
            "failed_core_bones_25_degrees": [
                delta.source_bone
                for delta in apose_report.bone_deltas
                if delta.source_bone in HUMANOID_CORE and delta.angular_delta_degrees > 25.0
            ],
            "bone_deltas": _sort_bone_deltas(apose_report),
        },
        "reverse_rename_validation": {
            "reverse_map_path": str(spec.path),
            "errors": reverse_errors,
            "mapped_source_present_count": len(set(spec.rename_pairs) & source_bones),
            "mapped_source_total": len(spec.rename_pairs),
            "missing_mapped_source": missing_mapped_source,
            "missing_mapped_target": missing_mapped_target,
            "dropped_ue5_bones_present": sorted((set(spec.ue5_only_bones_dropped) | set(spec.synthetic_helper_bones_dropped)) & source_bones),
            "unaccounted_source_bones": unaccounted,
            "unaccounted_core_bones": unaccounted_core,
        },
        "pmbam_reference": {
            "path": str(args.pmbam_contract),
            "bone_count": len(target_bones),
            "skeleton_id": pmbam.get("skeleton_id"),
        },
    }

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(args.output_md, payload)
    print(f"[GATE2_VALIDATE] {payload['status']} {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
