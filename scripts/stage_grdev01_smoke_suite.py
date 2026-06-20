"""Stage the grdev01 Map Studio smoke-module variant suite.

This is a thin command-line wrapper around the native Map Studio smoke builder.
It intentionally stages packages for manual in-game testing instead of marking
anything as game-tested.  Each supported geometry variant writes a separate
candidate `grdev01.mod`; copy and test one variant at a time with `warp grdev01`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_PATHS = (
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Resources/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Rendering/Python",
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
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "map_studio" / "grdev01_variant_suite",
        help="Directory that receives the staged variant packages and suite files.",
    )
    parser.add_argument(
        "--game",
        default="K1",
        choices=("K1", "K2", "k1", "k2"),
        help="Game target used for metadata and optional Modules-folder detection.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder to show in the checklist. The suite does not auto-copy variants.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=None,
        help="Optional KOTOR install root used only when --auto-detect-game-modules-dir is set.",
    )
    parser.add_argument(
        "--settings-path",
        type=Path,
        default=None,
        help="Optional GhostRigger settings.json used only when --auto-detect-game-modules-dir is set.",
    )
    parser.add_argument(
        "--auto-detect-game-modules-dir",
        action="store_true",
        help="Resolve the Modules folder for checklist text without copying all variants into the game.",
    )
    parser.add_argument(
        "--no-rectangular",
        action="store_true",
        help="Skip the rectangular-composition baseline variant.",
    )
    parser.add_argument(
        "--no-floor-plan",
        action="store_true",
        help="Skip the floor-plan/opening variant.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable summary instead of the human checklist summary.",
    )
    return parser


def _path_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def _result_summary(result: Any) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    for variant in result.variants:
        variants.append(
            {
                "variant_id": variant.variant_id,
                "label": variant.label,
                "room_geometry_mode": variant.room_geometry_mode,
                "ok": bool(variant.prep_result.ok),
                "code": variant.prep_result.code,
                "module_path": variant.module_path,
                "pack_manifest_path": variant.pack_manifest_path,
                "checklist_path": variant.checklist_path,
                "proof_manifest_path": variant.proof_manifest_path,
                "warnings": list(variant.warnings),
                "blocking_issues": list(variant.blocking_issues),
            }
        )
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "output_dir": result.output_dir,
        "suite_checklist_path": result.suite_checklist_path,
        "suite_manifest_path": result.suite_manifest_path,
        "resolved_modules_dir": result.resolved_modules_dir,
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
        "variants": variants,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 smoke variant suite: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Output directory: {summary['output_dir']}")
    print(f"Suite checklist: {summary['suite_checklist_path']}")
    print(f"Suite manifest: {summary['suite_manifest_path']}")
    if summary["resolved_modules_dir"]:
        print(f"Checklist copy target: {Path(summary['resolved_modules_dir']) / 'grdev01.mod'}")
    print("")
    for variant in summary["variants"]:
        variant_status = "OK" if variant["ok"] else "BLOCKED"
        print(f"- {variant['variant_id']}: {variant_status} ({variant['code']})")
        print(f"  {variant['label']}")
        print(f"  Module: {variant['module_path']}")
        print(f"  Pack manifest: {variant['pack_manifest_path']}")
        print(f"  Proof manifest: {variant['proof_manifest_path']}")
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
    print("")
    print("Manual proof remains required: copy one variant's grdev01.mod at a time, then run `warp grdev01` in KOTOR.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _install_payload_paths()
    from src.core.modules.dev_module_smoke import (  # noqa: WPS433
        DevModuleSmokeVariantSuiteRequest,
        prepare_dev_test_module_variant_suite,
    )

    request = DevModuleSmokeVariantSuiteRequest(
        output_dir=str(args.output_dir),
        game=str(args.game).upper(),
        include_rectangular_composition=not args.no_rectangular,
        include_floor_plan_opening=not args.no_floor_plan,
        game_modules_dir=_path_text(args.game_modules_dir),
        game_root_dir=_path_text(args.game_root_dir),
        settings_path=_path_text(args.settings_path),
        auto_detect_game_modules_dir=bool(args.auto_detect_game_modules_dir),
    )
    result = prepare_dev_test_module_variant_suite(request)
    summary = _result_summary(result)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
