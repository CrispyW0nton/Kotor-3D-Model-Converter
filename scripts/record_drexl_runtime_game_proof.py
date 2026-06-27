"""Record live KOTOR II proof for the Drexl re-UV replacement package."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECK_FLAGS = {
    "game_launches_with_override": "--game-launches-with-override",
    "ambient_drexl_spawns": "--ambient-drexl-spawns",
    "new_texture_visible": "--new-texture-visible",
    "uv_alignment_ok": "--uv-alignment-ok",
    "idle_animation_ok": "--idle-animation-ok",
    "walk_animation_ok": "--walk-animation-ok",
    "scale_orientation_ok": "--scale-orientation-ok",
    "camera_hook_ok": "--camera-hook-ok",
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        required=True,
        help="Path to c_drexlf_runtime_game_proof_manifest.json.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="Screenshot or video captured from the live KOTOR II Drexl test.",
    )
    parser.add_argument("--tester", default="", help="Name or handle of the tester recording proof.")
    parser.add_argument("--notes", default="", help="Short notes about the observed result.")
    parser.add_argument(
        "--allow-missing-evidence",
        action="store_true",
        help="Record an incomplete attempt even if the evidence file is not present.",
    )
    for check_id, flag in CHECK_FLAGS.items():
        parser.add_argument(flag, dest=check_id, action="store_true")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - argparse displays this path.
        raise SystemExit(f"Could not read proof manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Proof manifest is not a JSON object.")
    return payload


def _update_checks(manifest: dict[str, Any], args: argparse.Namespace) -> list[str]:
    missing: list[str] = []
    checks = manifest.get("manual_acceptance_checks")
    if not isinstance(checks, list):
        checks = []
        manifest["manual_acceptance_checks"] = checks
    by_id = {str(check.get("id")): check for check in checks if isinstance(check, dict)}
    for check_id in CHECK_FLAGS:
        accepted = bool(getattr(args, check_id))
        check = by_id.get(check_id)
        if check is None:
            check = {"id": check_id, "evidence": ""}
            checks.append(check)
        check["accepted"] = accepted
        if accepted:
            check["accepted_utc"] = datetime.now(timezone.utc).isoformat()
        else:
            missing.append(check_id)
    return missing


def _record_evidence(manifest: dict[str, Any], args: argparse.Namespace) -> bool:
    evidence = args.evidence
    exists = evidence.is_file()
    entries = manifest.get("evidence_files")
    if not isinstance(entries, list):
        entries = []
        manifest["evidence_files"] = entries
    entry = {
        "path": str(evidence),
        "exists": exists,
        "tester": str(args.tester),
        "notes": str(args.notes),
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
    }
    if exists:
        entry["bytes"] = evidence.stat().st_size
    entries.append(entry)
    return exists


def _summary(manifest: dict[str, Any], proof_manifest: Path, evidence_exists: bool, missing: list[str]) -> dict[str, Any]:
    complete = evidence_exists and not missing
    manifest["game_runtime_verified"] = bool(complete)
    manifest["game_ready"] = bool(complete)
    manifest["status"] = "runtime_game_verified" if complete else "runtime_test_incomplete"
    manifest["updated_utc"] = datetime.now(timezone.utc).isoformat()
    if complete:
        manifest["remaining_required_proof"] = ""
    return {
        "ok": complete,
        "status": manifest["status"],
        "proof_manifest": str(proof_manifest),
        "evidence_exists": evidence_exists,
        "missing_checks": missing,
        "game_runtime_verified": bool(manifest["game_runtime_verified"]),
        "game_ready": bool(manifest["game_ready"]),
    }


def _print_human(summary: dict[str, Any]) -> None:
    result = "GAME-VERIFIED" if summary["ok"] else "INCOMPLETE"
    print(f"Drexl runtime proof: {result} ({summary['status']})")
    print(f"Proof manifest: {summary['proof_manifest']}")
    print(f"Evidence exists: {summary['evidence_exists']}")
    if summary["missing_checks"]:
        print("Missing checks:")
        for check in summary["missing_checks"]:
            print(f"- {check}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    manifest = _load_manifest(args.proof_manifest)
    evidence_exists = _record_evidence(manifest, args)
    missing = _update_checks(manifest, args)
    if not evidence_exists and not args.allow_missing_evidence:
        missing = ["evidence_file_missing", *missing]
    summary = _summary(manifest, args.proof_manifest, evidence_exists, missing)
    args.proof_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
