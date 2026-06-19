"""Record in-game proof for a staged grdev01 Map Studio smoke module.

Run this only after testing the module in KOTOR with `warp grdev01` and
capturing screenshot or video evidence.  The proof manifest and pack manifest
are marked game-tested only when every required acceptance check is supplied.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATHS = (
    "native/GhostRigger.Domain.Core.Modules/Python",
    "native/GhostRigger.Domain.Core.Game/Python",
    "native/GhostRigger.Domain.Core.Scene/Python",
    "native/GhostRigger.Domain.Core.Walkmesh/Python",
    "native/GhostRigger.Domain.Core.Geometry/Python",
    "native/GhostRigger.Domain.Core.Camera/Python",
    "native/GhostRigger.Domain.Core.Math/Python",
    "native/GhostRigger.Domain.Core.Lighting/Python",
    ".",
)


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        required=True,
        help="Path to the grdev01 proof manifest written by the install/staging command.",
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
        help="Screenshot or video captured from the actual KOTOR warp test.",
    )
    parser.add_argument("--tester", default="", help="Name or handle of the tester recording proof.")
    parser.add_argument("--notes", default="", help="Optional notes about the KOTOR build, install path, or result.")
    parser.add_argument(
        "--module-loads-in-game",
        action="store_true",
        help="Confirm `warp grdev01` loads the generated module in KOTOR.",
    )
    parser.add_argument(
        "--player-spawns-on-floor",
        action="store_true",
        help="Confirm the player appears on the generated floor, not in void.",
    )
    parser.add_argument(
        "--test-placeable-visible",
        action="store_true",
        help="Confirm the smoke-test placeable appears where expected.",
    )
    parser.add_argument(
        "--player-can-walk-on-floor",
        action="store_true",
        help="Confirm the player can walk across the generated floor.",
    )
    parser.add_argument(
        "--allow-missing-evidence",
        action="store_true",
        help="Record an incomplete proof attempt even if the evidence file is not present.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable summary instead of the human proof summary.",
    )
    return parser


def _result_summary(result: Any) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "proof_manifest_path": result.proof_manifest_path,
        "pack_manifest_path": result.pack_manifest_path,
        "evidence_path": result.evidence_path,
        "missing_checks": list(result.missing_checks),
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "GAME-TESTED" if summary["ok"] else "INCOMPLETE"
    print(f"grdev01 smoke proof: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Proof manifest: {summary['proof_manifest_path']}")
    print(f"Pack manifest: {summary['pack_manifest_path']}")
    print(f"Evidence: {summary['evidence_path']}")
    if summary["missing_checks"]:
        print("")
        print("Missing checks:")
        for check in summary["missing_checks"]:
            print(f"- {check}")
    if summary["warnings"]:
        print("")
        print("Warnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")
    if summary["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")
    if summary["ok"]:
        print("")
        print("The proof manifest and pack manifest now record this grdev01 package as game-tested.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _install_payload_paths()
    from src.core.modules.dev_module_smoke import DevModuleGameProofRequest, record_dev_module_game_proof  # noqa: WPS433

    result = record_dev_module_game_proof(
        DevModuleGameProofRequest(
            proof_manifest_path=str(args.proof_manifest),
            evidence_path=str(args.evidence),
            tester=str(args.tester),
            notes=str(args.notes),
            module_loads_in_game=bool(args.module_loads_in_game),
            player_spawns_on_floor=bool(args.player_spawns_on_floor),
            test_placeable_visible=bool(args.test_placeable_visible),
            player_can_walk_on_floor=bool(args.player_can_walk_on_floor),
            allow_missing_evidence=bool(args.allow_missing_evidence),
        )
    )
    summary = _result_summary(result)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
