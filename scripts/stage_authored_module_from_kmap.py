"""Stage an authored Map Studio KMAP module for manual KOTOR proof.

This script packages the `authored_module` section from a saved `.kmap`, writes
the install checklist/proof manifest, and optionally copies the generated MOD
into a KOTOR `Modules` folder. It never marks the module game-tested.
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
    "native/GhostRigger.Domain.Core.Level/Python",
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
    parser.add_argument("--kmap", type=Path, required=True, help="Saved KMAP file containing an authored_module section.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "map_studio" / "authored_module_stage",
        help="Directory that receives the staged package, checklist, and proof manifest.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder to copy the generated MOD into.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=None,
        help="Optional KOTOR install root used only with --auto-detect-game-modules-dir.",
    )
    parser.add_argument(
        "--settings-path",
        type=Path,
        default=None,
        help="Optional GhostRigger settings.json used only with --auto-detect-game-modules-dir.",
    )
    parser.add_argument(
        "--auto-detect-game-modules-dir",
        action="store_true",
        help="Try to resolve the KOTOR Modules folder from settings or the supplied game root.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Back up and replace an existing module in Modules.")
    parser.add_argument("--dry-run", action="store_true", help="Build package/checklist but do not copy into Modules.")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _path_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def _error_summary(*, code: str, message: str, kmap_path: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "kmap_path": kmap_path,
        "module_root": "",
        "module_path": "",
        "pack_manifest_path": "",
        "installed_module_path": "",
        "backup_module_path": "",
        "checklist_path": "",
        "proof_manifest_path": "",
        "warnings": [],
        "blocking_issues": [message],
        "resources": [],
    }


def _result_summary(result: Any, *, kmap_path: Path) -> dict[str, Any]:
    export_result = result.export_result
    resources = []
    if export_result is not None:
        resources = [
            {
                "resref": resource.resref,
                "restype": resource.restype,
                "size": resource.size,
                "source": resource.source,
            }
            for resource in export_result.resources
        ]
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "kmap_path": str(kmap_path),
        "module_root": export_result.module_root if export_result is not None else "",
        "module_path": export_result.module_path if export_result is not None else "",
        "pack_manifest_path": export_result.manifest_path if export_result is not None else "",
        "installed_module_path": result.installed_module_path,
        "backup_module_path": result.backup_module_path,
        "resolved_modules_dir": result.resolved_modules_dir,
        "checklist_path": result.checklist_path,
        "proof_manifest_path": result.proof_manifest_path,
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
        "resources": resources,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"Authored KMAP module stage: {status} ({summary['code']})")
    print(summary["message"])
    print(f"KMAP: {summary['kmap_path']}")
    print(f"Module root: {summary['module_root'] or '(not available)'}")
    print(f"Package: {summary['module_path'] or '(not written)'}")
    print(f"Pack manifest: {summary['pack_manifest_path'] or '(not written)'}")
    print(f"Checklist: {summary['checklist_path'] or '(not written)'}")
    print(f"Proof manifest: {summary['proof_manifest_path'] or '(not written)'}")
    if summary.get("installed_module_path"):
        print(f"Installed module: {summary['installed_module_path']}")
    if summary.get("backup_module_path"):
        print(f"Backup: {summary['backup_module_path']}")
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
        print("Manual proof remains required: install the MOD, run the warp command, then record proof with record_authored_module_game_proof.py.")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    _install_payload_paths()
    from src.core.level.kmap_serializer import KMapSerializer  # noqa: WPS433
    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install  # noqa: WPS433
    from src.core.modules.authored_module_kmap_bridge import authored_project_from_kmap_payload  # noqa: WPS433

    try:
        kmap = KMapSerializer.load(args.kmap)
    except Exception as exc:
        summary = _error_summary(code="kmap_load_failed", message=f"KMAP could not be loaded: {exc}", kmap_path=str(args.kmap))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(summary)
        return 1
    payload = dict(getattr(kmap, "extra_sections", {}) or {}).get("authored_module")
    if payload is None:
        summary = _error_summary(
            code="authored_module_missing",
            message="KMAP does not contain an authored_module section. Use Map Studio to create an authored room first.",
            kmap_path=str(args.kmap),
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(summary)
        return 1
    try:
        authored = authored_project_from_kmap_payload(
            payload,
            fallback_name=str(getattr(kmap, "name", "") or "new_level"),
            fallback_game=str(getattr(kmap, "game", "") or "K1"),
        )
    except Exception as exc:
        summary = _error_summary(code="authored_module_parse_failed", message=f"authored_module could not be parsed: {exc}", kmap_path=str(args.kmap))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(summary)
        return 1

    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=authored,
            output_dir=str(args.output_dir),
            game_modules_dir=_path_text(args.game_modules_dir),
            game_root_dir=_path_text(args.game_root_dir),
            settings_path=_path_text(args.settings_path),
            auto_detect_game_modules_dir=bool(args.auto_detect_game_modules_dir),
            overwrite=bool(args.overwrite),
            dry_run=bool(args.dry_run),
        )
    )
    summary = _result_summary(result, kmap_path=args.kmap)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
