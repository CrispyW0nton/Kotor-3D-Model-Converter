"""Install one grdev01 Map Studio smoke-module variant for in-game proof.

This command builds one selected `grdev01.mod` export candidate, optionally
copies it into a KOTOR `Modules` folder, and writes the proof manifest/checklist
needed for the manual `warp grdev01` smoke test.  It never installs both smoke
variants at once because they intentionally share the same module resref.
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
VARIANT_ALIASES = {
    "rectangular": ("rectangular_composition", "Rectangular composition baseline", "rectangular_composition"),
    "rectangular_composition": ("rectangular_composition", "Rectangular composition baseline", "rectangular_composition"),
    "floor-plan": ("floor_plan_opening", "Floor-plan extrusion with wall opening", "floor_plan"),
    "floor_plan": ("floor_plan_opening", "Floor-plan extrusion with wall opening", "floor_plan"),
    "floor_plan_opening": ("floor_plan_opening", "Floor-plan extrusion with wall opening", "floor_plan"),
}


def _install_payload_paths() -> None:
    for rel in PAYLOAD_PATHS:
        path = str((ROOT / rel).resolve())
        if path not in sys.path:
            sys.path.insert(0, path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        default="rectangular_composition",
        choices=tuple(VARIANT_ALIASES),
        help="The single smoke-module geometry variant to build and optionally install.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory that receives the selected variant package and proof files.",
    )
    parser.add_argument(
        "--game",
        default="K1",
        choices=("K1", "K2", "k1", "k2"),
        help="Game target used for package metadata and optional Modules-folder detection.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="KOTOR Modules folder that should receive the selected grdev01.mod.",
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
        help="Find the KOTOR Modules folder from settings/default locations and install there if safe.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing grdev01.mod in the target Modules folder.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and preflight the selected variant without copying it into Modules.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable summary instead of the human install summary.",
    )
    return parser


def _path_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def _variant_spec(alias: str) -> tuple[str, str, str]:
    return VARIANT_ALIASES[alias]


def _proof_launch_handoff_value(proof_manifest_path: str, key: str) -> str:
    if not proof_manifest_path:
        return ""
    try:
        proof = json.loads(Path(proof_manifest_path).read_text(encoding="utf-8"))
    except Exception:
        return ""
    handoff = proof.get("launch_handoff") if isinstance(proof.get("launch_handoff"), dict) else {}
    return str(handoff.get(key) or "")


def _result_summary(result: Any, *, variant_id: str, variant_label: str, room_geometry_mode: str) -> dict[str, Any]:
    export = result.export_result
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "variant_id": variant_id,
        "variant_label": variant_label,
        "room_geometry_mode": room_geometry_mode,
        "module_root": export.module_root if export else "",
        "module_path": export.module_path if export else "",
        "pack_manifest_path": export.manifest_path if export else "",
        "installed_module_path": result.installed_module_path,
        "backup_module_path": getattr(result, "backup_module_path", ""),
        "resolved_modules_dir": result.resolved_modules_dir,
        "resolved_game_root_dir": getattr(result, "resolved_game_root_dir", ""),
        "launch_helper_command": getattr(result, "launch_helper_command", ""),
        "elevated_launch_script_path": getattr(result, "elevated_launch_script_path", ""),
        "evidence_capture_command": _proof_launch_handoff_value(result.proof_manifest_path, "evidence_capture_command"),
        "proof_recording_script_path": getattr(result, "proof_recording_script_path", ""),
        "checklist_path": result.checklist_path,
        "proof_manifest_path": result.proof_manifest_path,
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 smoke variant install: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Variant: {summary['variant_id']} - {summary['variant_label']}")
    print(f"Built module: {summary['module_path']}")
    print(f"Pack manifest: {summary['pack_manifest_path']}")
    if summary["resolved_modules_dir"]:
        print(f"Resolved Modules folder: {summary['resolved_modules_dir']}")
    if summary.get("resolved_game_root_dir"):
        print(f"Resolved game root: {summary['resolved_game_root_dir']}")
    if summary["installed_module_path"]:
        print(f"Installed module: {summary['installed_module_path']}")
        if summary.get("backup_module_path"):
            print(f"Previous module backup: {summary['backup_module_path']}")
    else:
        print("Installed module: (not copied)")
    if summary.get("launch_helper_command"):
        print(f"Launch dry-run helper: {summary['launch_helper_command']}")
    if summary.get("elevated_launch_script_path"):
        print(f"Elevated launch helper: {summary['elevated_launch_script_path']}")
    if summary.get("evidence_capture_command"):
        print(f"Evidence capture command: {summary['evidence_capture_command']}")
    if summary.get("proof_recording_script_path"):
        print(f"Proof recorder: {summary['proof_recording_script_path']}")
    print(f"Checklist: {summary['checklist_path']}")
    print(f"Proof manifest: {summary['proof_manifest_path']}")
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
    print("Next proof step: launch KOTOR, run `warp grdev01`, verify floor/placeable/walkability, and capture evidence.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    variant_id, variant_label, room_geometry_mode = _variant_spec(args.variant)
    output_dir = args.output_dir or ROOT / "artifacts" / "map_studio" / "grdev01_install" / variant_id

    _install_payload_paths()
    from src.core.modules.dev_module_smoke import (  # noqa: WPS433
        DevModuleInstallPrepRequest,
        DevModuleSmokeRequest,
        prepare_dev_test_module_install,
    )

    game = str(args.game).upper()
    result = prepare_dev_test_module_install(
        DevModuleInstallPrepRequest(
            output_dir=str(output_dir),
            game=game,
            game_modules_dir=_path_text(args.game_modules_dir),
            game_root_dir=_path_text(args.game_root_dir),
            settings_path=_path_text(args.settings_path),
            auto_detect_game_modules_dir=bool(args.auto_detect_game_modules_dir),
            overwrite=bool(args.overwrite),
            dry_run=bool(args.dry_run),
            smoke_request=DevModuleSmokeRequest(
                output_dir=str(output_dir),
                game=game,
                room_geometry_mode=room_geometry_mode,
            ),
        )
    )
    summary = _result_summary(
        result,
        variant_id=variant_id,
        variant_label=variant_label,
        room_geometry_mode=room_geometry_mode,
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
