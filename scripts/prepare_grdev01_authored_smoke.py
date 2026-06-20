"""Prepare the from-scratch grdev01 authored module for KOTOR smoke testing.

This is the one-command setup path for the first Map Studio proof loop:

1. Create or refresh a saved grdev01 authored KMAP.
2. Package the authored module into grdev01.mod.
3. Write the manual checklist and proof manifest.
4. Optionally copy the package into a KOTOR Modules folder.

It does not mark the module game-tested. Run KOTOR, `warp grdev01`, capture
evidence, then use `record_authored_module_game_proof.py`.
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
        default=ROOT / "artifacts" / "map_studio" / "grdev01_authored_smoke",
        help="Directory that receives the KMAP, package, checklist, and proof manifest.",
    )
    parser.add_argument(
        "--kmap-path",
        type=Path,
        default=None,
        help="Optional explicit KMAP path. Defaults to <output-dir>/grdev01.kmap.",
    )
    parser.add_argument("--module-root", default="grdev01", help="Module resref to generate.")
    parser.add_argument("--game", default="K1", choices=("K1", "K2", "k1", "k2"), help="Target game.")
    parser.add_argument("--author", default="", help="Optional KMAP author field.")
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
    parser.add_argument(
        "--overwrite-kmap",
        action="store_true",
        help="Replace an existing generated KMAP.",
    )
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Back up and replace an existing module in the target Modules folder.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Package and write proof files without copying into Modules.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _path_text(path: Path | None) -> str:
    return str(path) if path is not None else ""


def _error_summary(*, code: str, message: str, output_dir: Path, kmap_path: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "code": code,
        "message": message,
        "output_dir": str(output_dir),
        "kmap_path": str(kmap_path),
        "module_root": "",
        "module_path": "",
        "pack_manifest_path": "",
        "installed_module_path": "",
        "backup_module_path": "",
        "resolved_modules_dir": "",
        "resolved_game_root_dir": "",
        "launch_helper_command": "",
        "elevated_launch_script_path": "",
        "proof_recording_script_path": "",
        "checklist_path": "",
        "proof_manifest_path": "",
        "warnings": [],
        "blocking_issues": [message],
        "next_actions": [],
    }


def _resource_summary(export_result: Any) -> list[dict[str, Any]]:
    if export_result is None:
        return []
    return [
        {
            "resref": item.resref,
            "restype": item.restype,
            "size": item.size,
            "source": item.source,
        }
        for item in export_result.resources
    ]


def _proof_launch_handoff_value(proof_manifest_path: str, key: str) -> str:
    if not proof_manifest_path:
        return ""
    try:
        proof = json.loads(Path(proof_manifest_path).read_text(encoding="utf-8"))
    except Exception:
        return ""
    handoff = proof.get("launch_handoff") if isinstance(proof.get("launch_handoff"), dict) else {}
    return str(handoff.get(key) or "")


def _summary(
    *,
    result: Any,
    output_dir: Path,
    kmap_path: Path,
    module_root: str,
    game: str,
) -> dict[str, Any]:
    export_result = result.export_result
    proof_manifest = result.proof_manifest_path
    next_actions = []
    if result.installed_module_path:
        next_actions.append(f"Launch {game} and run `warp {module_root}`.")
    else:
        next_actions.append(f"Copy `{export_result.module_path if export_result else module_root + '.mod'}` into a KOTOR `Modules` folder.")
        next_actions.append(f"Launch {game} and run `warp {module_root}`.")
    next_actions.append("Confirm the module loads, the player is on the floor, the test placeable appears, and walking works.")
    proof_recorder = str(getattr(result, "proof_recording_script_path", "") or "")
    if proof_recorder:
        next_actions.append(f"After capturing evidence, run `{proof_recorder}` and paste the screenshot/video path.")
    next_actions.append(
        "Record proof with "
        f"`python scripts/record_authored_module_game_proof.py --proof-manifest \"{proof_manifest}\" --evidence <screenshot-or-video> "
        "--module-loads-in-game --player-spawns-on-floor --test-placeable-visible --player-can-walk-on-floor`."
    )
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "output_dir": str(output_dir),
        "kmap_path": str(kmap_path),
        "module_root": module_root,
        "game": game,
        "module_path": export_result.module_path if export_result is not None else "",
        "pack_manifest_path": export_result.manifest_path if export_result is not None else "",
        "installed_module_path": result.installed_module_path,
        "backup_module_path": result.backup_module_path,
        "resolved_modules_dir": result.resolved_modules_dir,
        "resolved_game_root_dir": getattr(result, "resolved_game_root_dir", ""),
        "launch_helper_command": getattr(result, "launch_helper_command", ""),
        "elevated_launch_script_path": getattr(result, "elevated_launch_script_path", ""),
        "evidence_capture_command": _proof_launch_handoff_value(result.proof_manifest_path, "evidence_capture_command"),
        "proof_recording_script_path": getattr(result, "proof_recording_script_path", ""),
        "checklist_path": result.checklist_path,
        "proof_manifest_path": result.proof_manifest_path,
        "resources": _resource_summary(export_result),
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
        "next_actions": next_actions,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 authored smoke prep: {status} ({summary['code']})")
    print(summary["message"])
    print(f"KMAP: {summary['kmap_path']}")
    print(f"Package: {summary['module_path'] or '(not written)'}")
    print(f"Pack manifest: {summary['pack_manifest_path'] or '(not written)'}")
    print(f"Checklist: {summary['checklist_path'] or '(not written)'}")
    print(f"Proof manifest: {summary['proof_manifest_path'] or '(not written)'}")
    if summary.get("resolved_game_root_dir"):
        print(f"Resolved game root: {summary['resolved_game_root_dir']}")
    if summary.get("launch_helper_command"):
        print(f"Launch dry-run helper: {summary['launch_helper_command']}")
    if summary["elevated_launch_script_path"]:
        print(f"Elevated launcher: {summary['elevated_launch_script_path']}")
    if summary.get("evidence_capture_command"):
        print(f"Evidence capture command: {summary['evidence_capture_command']}")
    if summary.get("proof_recording_script_path"):
        print(f"Proof recorder: {summary['proof_recording_script_path']}")
    if summary["installed_module_path"]:
        print(f"Installed module: {summary['installed_module_path']}")
    if summary["backup_module_path"]:
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
    if summary["next_actions"]:
        print("")
        print("Next actions:")
        for action in summary["next_actions"]:
            print(f"- {action}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_dir = args.output_dir
    kmap_path = args.kmap_path or output_dir / "grdev01.kmap"
    module_root = str(args.module_root or "grdev01").strip() or "grdev01"
    game = str(args.game or "K1").upper()
    if kmap_path.exists() and not args.overwrite_kmap:
        summary = _error_summary(
            code="kmap_exists",
            message=f"KMAP already exists: {kmap_path}. Re-run with --overwrite-kmap to replace it.",
            output_dir=output_dir,
            kmap_path=kmap_path,
        )
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            _print_human_summary(summary)
        return 1

    _install_payload_paths()
    from src.core.level import new_kmap_project  # noqa: WPS433
    from src.core.level.kmap_serializer import KMapSerializer  # noqa: WPS433
    from src.core.modules.authored_module_export import AuthoredModuleInstallPrepRequest, prepare_authored_module_install  # noqa: WPS433
    from src.core.modules.authored_module_kmap_bridge import (  # noqa: WPS433
        authored_project_from_kmap_payload,
        create_dev_test_authored_module_payload,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    project = new_kmap_project(name=module_root, game=game, author=str(args.author or ""))
    payload = create_dev_test_authored_module_payload(module_root=module_root, game=game)
    project.extra_sections["authored_module"] = payload
    KMapSerializer.save(project, kmap_path)
    authored = authored_project_from_kmap_payload(payload, fallback_name=module_root, fallback_game=game)
    result = prepare_authored_module_install(
        AuthoredModuleInstallPrepRequest(
            project=authored,
            output_dir=str(output_dir),
            game_modules_dir=_path_text(args.game_modules_dir),
            game_root_dir=_path_text(args.game_root_dir),
            settings_path=_path_text(args.settings_path),
            auto_detect_game_modules_dir=bool(args.auto_detect_game_modules_dir),
            overwrite=bool(args.overwrite_module),
            dry_run=bool(args.dry_run),
        )
    )
    summary = _summary(result=result, output_dir=output_dir, kmap_path=kmap_path, module_root=module_root, game=game)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
