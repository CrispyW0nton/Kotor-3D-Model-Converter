"""Audit the current grdev01 Map Studio smoke-test status.

This command reads the proof manifest, checks the pack manifest, re-verifies
the staged `grdev01.mod` package, and optionally compares an installed module
copy in a KOTOR `Modules` folder.  It does not mark anything game-tested; it
only reports which proof gates are satisfied and which still need evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_RUNTIME_RESOURCE_KEYS = (
    "grdev01.are",
    "grdev01.git",
    "module.ifo",
    "grdev01.pth",
    "grdev01.lyt",
    "grdev01.vis",
    "grdev01_room01.mdl",
    "grdev01_room01.mdx",
    "grdev01_room01.wok",
)
PROOF_EVIDENCE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
    ".webm",
}
PAYLOAD_PATHS = (
    "native/GhostRigger.Core.Scene.Modules/Python",
    "native/GhostRigger.Core.Resources.Game/Python",
    "native/GhostRigger.Core.Scene/Python",
    "native/GhostRigger.Core.Scene.Walkmesh/Python",
    "native/GhostRigger.Core.Math.Geometry/Python",
    "native/GhostRigger.Core.Math.Camera/Python",
    "native/GhostRigger.Core.Math/Python",
    "native/GhostRigger.Core.Rendering.Lighting/Python",
    "native/GhostRigger.Core.Automation.MCP/Python/src",
    ".",
)
KOTORMCP_REQUIRED_RESOURCE_TYPES = ("ARE", "GIT", "IFO", "LYT", "PTH", "VIS", "MDL", "WOK")


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
        help="Path to the grdev01 proof manifest written by install/staging.",
    )
    parser.add_argument(
        "--module-path",
        type=Path,
        default=None,
        help="Optional explicit grdev01.mod package path. Defaults to the proof manifest package path.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder used to check the installed grdev01.mod copy.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable status payload instead of a human summary.",
    )
    parser.add_argument(
        "--kotormcp",
        action="store_true",
        help="Also query KotorMCP against the installed game to confirm grdev01 is visible as a module.",
    )
    return parser


def _load_json(path: Path) -> tuple[dict[str, Any], str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except Exception as exc:
        return {}, f"{path} could not be read as JSON: {exc}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verification_summary(module_path: Path) -> dict[str, Any]:
    if not module_path.is_file():
        return {
            "ok": False,
            "code": "module_missing",
            "module_path": str(module_path),
            "blocking_issues": [f"Module package does not exist: {module_path}"],
        }
    _install_payload_paths()
    from src.core.modules.dev_module_smoke import verify_dev_test_module_package  # noqa: WPS433

    result = verify_dev_test_module_package(module_path)
    resources = [
        {
            "resref": resource.resref,
            "restype": resource.restype,
            "key": f"{resource.resref}.{resource.restype}",
            "size": resource.size,
            "offset": resource.offset,
        }
        for resource in result.resources
    ]
    return {
        "ok": bool(result.ok),
        "code": result.code,
        "message": result.message,
        "module_path": result.module_path,
        "module_sha256": _sha256(module_path),
        "resources": resources,
        "resource_keys": sorted(resource["key"] for resource in resources),
        "parsed_gff": list(result.parsed_gff),
        "parsed_wok": list(result.parsed_wok),
        "model_pairs": list(result.model_pairs),
        "path_point_count": result.path_point_count,
        "path_connection_count": result.path_connection_count,
        "warnings": list(result.warnings),
        "blocking_issues": list(result.blocking_issues),
    }


def _runtime_archive_summary(verification: dict[str, Any]) -> dict[str, Any]:
    resource_keys = set(verification.get("resource_keys") or [])
    missing = [key for key in REQUIRED_RUNTIME_RESOURCE_KEYS if key not in resource_keys]
    return {
        "required_resource_keys": list(REQUIRED_RUNTIME_RESOURCE_KEYS),
        "missing_required_resource_keys": missing,
        "engine_ifo_key_ok": "module.ifo" in resource_keys,
        "room_model_pair_ok": "grdev01_room01.mdl" in resource_keys and "grdev01_room01.mdx" in resource_keys,
        "walkmesh_key_ok": "grdev01_room01.wok" in resource_keys,
        "layout_keys_ok": "grdev01.lyt" in resource_keys and "grdev01.vis" in resource_keys,
        "path_key_ok": "grdev01.pth" in resource_keys,
    }


def _parse_kotormcp_payload(result: dict[str, Any]) -> dict[str, Any]:
    text = result.get("text") if isinstance(result, dict) else ""
    if not isinstance(text, str) or not text:
        return {"error": f"Unexpected KotorMCP response: {result!r}"}
    try:
        payload = json.loads(text)
    except Exception as exc:
        return {"error": f"KotorMCP response was not JSON: {exc}"}
    return payload if isinstance(payload, dict) else {"error": f"Unexpected KotorMCP payload: {payload!r}"}


def _run_kotormcp_module_tool(name: str, arguments: dict[str, Any], *, game_root_dir: str = "") -> dict[str, Any]:
    _install_payload_paths()
    import asyncio  # noqa: WPS433
    import os  # noqa: WPS433

    from kotormcp.tools import handle_tool  # noqa: WPS433

    game = str(arguments.get("game") or "").lower()
    env_name = "K2_PATH" if game == "k2" else "K1_PATH"
    previous_env = os.environ.get(env_name)
    if game_root_dir:
        os.environ[env_name] = game_root_dir
    try:
        result = asyncio.run(handle_tool(name, arguments))
    finally:
        if game_root_dir:
            if previous_env is None:
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = previous_env
    return _parse_kotormcp_payload(result)


def _kotormcp_summary(*, enabled: bool, module_root: str, game: str, game_root_dir: str = "") -> dict[str, Any]:
    if not enabled:
        return {
            "checked": False,
            "ok": False,
            "available": False,
            "module_root": module_root,
            "game": game,
            "resource_count": 0,
            "resources": [],
            "missing_required_types": [],
            "warnings": [],
            "blocking_issues": [],
        }

    game_arg = "k2" if str(game).upper() == "K2" else "k1"
    warnings: list[str] = []
    blocking: list[str] = []
    try:
        resources = _run_kotormcp_module_tool(
            "kotor_module_resources",
            {"game": game_arg, "module_root": module_root, "limit": 500, "offset": 0},
            game_root_dir=game_root_dir,
        )
        describe = _run_kotormcp_module_tool(
            "kotor_describe_module",
            {"game": game_arg, "module_root": module_root},
            game_root_dir=game_root_dir,
        )
    except Exception as exc:
        return {
            "checked": True,
            "ok": False,
            "available": False,
            "module_root": module_root,
            "game": game_arg.upper(),
            "resource_count": 0,
            "resources": [],
            "missing_required_types": list(KOTORMCP_REQUIRED_RESOURCE_TYPES),
            "warnings": [],
            "blocking_issues": [f"KotorMCP could not run: {exc}"],
        }

    if resources.get("error"):
        blocking.append(str(resources["error"]))
    if describe.get("error"):
        blocking.append(str(describe["error"]))

    items = resources.get("items") if isinstance(resources.get("items"), list) else []
    seen_types = {str(item.get("type") or "").upper() for item in items if isinstance(item, dict)}
    missing_types = [restype for restype in KOTORMCP_REQUIRED_RESOURCE_TYPES if restype not in seen_types]
    if missing_types:
        blocking.append("KotorMCP did not see required resource types: " + ", ".join(missing_types))

    area_info = describe.get("area_info") if isinstance(describe.get("area_info"), dict) else {}
    if area_info.get("error"):
        warnings.append(f"KotorMCP area summary warning: {area_info['error']}")

    model_buffer_alias = ""
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("resref") or "").lower() == "grdev01_room01" and str(item.get("type") or "").upper() in {"MDX", "THG"}:
            model_buffer_alias = str(item.get("type") or "").upper()
            break

    return {
        "checked": True,
        "ok": not blocking,
        "available": True,
        "module_root": str(resources.get("module_root") or module_root),
        "game": game_arg.upper(),
        "resource_count": int(resources.get("total") or resources.get("count") or len(items)),
        "resources": items,
        "type_breakdown": describe.get("type_breakdown") if isinstance(describe.get("type_breakdown"), dict) else {},
        "missing_required_types": missing_types,
        "model_buffer_entry_type": model_buffer_alias,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _installed_summary(*, module_path: Path, proof: dict[str, Any], game_modules_dir: Path | None) -> dict[str, Any]:
    install = proof.get("install") if isinstance(proof.get("install"), dict) else {}
    installed_path_text = str(install.get("installed_module_path") or "")
    backup_path_text = str(install.get("backup_module_path") or "")
    if game_modules_dir is not None:
        installed_path_text = str(game_modules_dir / "grdev01.mod")
    if not installed_path_text:
        return {
            "checked": False,
            "exists": False,
            "matches_package": False,
            "installed_module_path": "",
            "backup_module_path": backup_path_text,
            "package_sha256": _sha256(module_path) if module_path.is_file() else "",
            "installed_sha256": "",
        }
    installed_path = Path(installed_path_text)
    exists = installed_path.is_file()
    matches = False
    package_sha = _sha256(module_path) if module_path.is_file() else ""
    installed_sha = _sha256(installed_path) if exists else ""
    if exists and module_path.is_file():
        matches = installed_sha == package_sha
    return {
        "checked": True,
        "exists": exists,
        "matches_package": matches,
        "installed_module_path": str(installed_path),
        "backup_module_path": backup_path_text,
        "package_sha256": package_sha,
        "installed_sha256": installed_sha,
    }


def _proof_summary(proof: dict[str, Any]) -> dict[str, Any]:
    required = list(proof.get("acceptance_checks") or [])
    game_test = proof.get("game_test") if isinstance(proof.get("game_test"), dict) else {}
    checks = game_test.get("checks") if isinstance(game_test.get("checks"), dict) else {}
    missing = list(game_test.get("missing_checks") or [name for name in required if not checks.get(name, False)])
    evidence_path = str(game_test.get("evidence_path") or "")
    evidence = Path(evidence_path) if evidence_path else None
    evidence_exists = bool(evidence is not None and evidence.is_file())
    evidence_accepted = bool(evidence_exists and evidence.stat().st_size > 0 and evidence.suffix.lower() in PROOF_EVIDENCE_EXTENSIONS)
    return {
        "game_tested": bool(proof.get("game_tested")),
        "manual_proof_required": bool(proof.get("manual_proof_required", True)),
        "required_checks": required,
        "checks": checks,
        "missing_checks": missing,
        "evidence_path": evidence_path,
        "evidence_exists": evidence_exists,
        "evidence_accepted": evidence_accepted,
    }


def _launch_handoff_summary(*, proof: dict[str, Any], proof_manifest: Path) -> dict[str, Any]:
    handoff = proof.get("launch_handoff") if isinstance(proof.get("launch_handoff"), dict) else {}
    warp_command = str(handoff.get("warp_command") or proof.get("warp_command") or "warp grdev01")
    game = str(handoff.get("game") or proof.get("game") or "K1").upper()
    proof_path = str(proof_manifest)
    task = str(proof.get("task") or "").strip().upper()
    recorder_script = str(handoff.get("proof_recording_script_path") or "")
    if task == "T2601":
        recorder_command_script = "scripts/record_grdev01_smoke_proof.py"
    else:
        recorder_command_script = "scripts/record_authored_module_game_proof.py"
    return {
        "game": "K2" if game == "K2" else "K1",
        "warp_command": warp_command,
        "resolved_modules_dir": str(handoff.get("resolved_modules_dir") or ""),
        "resolved_game_root_dir": str(handoff.get("resolved_game_root_dir") or ""),
        "expected_executable_path": str(handoff.get("expected_executable_path") or ""),
        "launch_helper_command": str(handoff.get("launch_helper_command") or ""),
        "elevated_launch_script_path": str(handoff.get("elevated_launch_script_path") or ""),
        "evidence_capture_command": str(handoff.get("evidence_capture_command") or ""),
        "proof_recording_script_path": recorder_script,
        "proof_recording_command_template": (
            f'python "{recorder_command_script}" --proof-manifest "{proof_path}" '
            "--evidence <screenshot-or-video> --module-loads-in-game --player-spawns-on-floor "
            "--test-placeable-visible --player-can-walk-on-floor"
        ),
    }


def _derive_status(*, verification: dict[str, Any], proof: dict[str, Any], installed: dict[str, Any]) -> tuple[str, bool]:
    if not verification.get("ok"):
        return "package_blocked", False
    if proof.get("game_tested") and proof.get("evidence_accepted") and not proof.get("missing_checks"):
        return "game_tested", True
    if installed.get("checked") and installed.get("exists") and not installed.get("matches_package"):
        return "installed_copy_mismatch", False
    if installed.get("checked") and installed.get("exists"):
        return "installed_ready_for_game_test", False
    return "ready_for_manual_install", False


def build_status(
    *,
    proof_manifest: Path,
    module_path: Path | None = None,
    game_modules_dir: Path | None = None,
    use_kotormcp: bool = False,
) -> dict[str, Any]:
    blocking: list[str] = []
    warnings: list[str] = []
    proof: dict[str, Any] = {}
    proof_error = ""
    if proof_manifest.is_file():
        proof, proof_error = _load_json(proof_manifest)
    else:
        proof_error = f"Proof manifest does not exist: {proof_manifest}"
    if proof_error:
        blocking.append(proof_error)
    package = proof.get("package") if isinstance(proof.get("package"), dict) else {}
    inferred_module = Path(str(package.get("module_path"))) if package.get("module_path") else None
    checked_module_path = module_path or inferred_module
    if checked_module_path is None:
        checked_module_path = Path("grdev01.mod")
        blocking.append("No module package path was supplied and the proof manifest did not name one.")
    verification = _verification_summary(checked_module_path)
    blocking.extend(verification.get("blocking_issues", []))
    runtime_archive = _runtime_archive_summary(verification)
    if runtime_archive["missing_required_resource_keys"]:
        blocking.append(
            "Module package is missing KOTOR runtime resources: "
            + ", ".join(runtime_archive["missing_required_resource_keys"])
        )
    proof_state = _proof_summary(proof)
    launch_handoff = _launch_handoff_summary(proof=proof, proof_manifest=proof_manifest)
    installed = _installed_summary(module_path=checked_module_path, proof=proof, game_modules_dir=game_modules_dir)
    module_root = str(proof.get("module_root") or package.get("module_root") or "grdev01")
    kotormcp = _kotormcp_summary(
        enabled=use_kotormcp,
        module_root=module_root,
        game=launch_handoff.get("game") or proof.get("game") or "K1",
        game_root_dir=launch_handoff.get("resolved_game_root_dir") or "",
    )
    if use_kotormcp and not kotormcp.get("ok"):
        blocking.extend(kotormcp.get("blocking_issues", []))
    if installed.get("checked") and not installed.get("exists"):
        warnings.append(f"Installed module copy was not found: {installed['installed_module_path']}")
    if installed.get("checked") and installed.get("exists") and not installed.get("matches_package"):
        blocking.append("Installed grdev01.mod does not match the staged package bytes.")
    status, complete = _derive_status(verification=verification, proof=proof_state, installed=installed)
    if blocking and status != "package_blocked":
        complete = False
    ready_for_game_launch = (
        status == "installed_ready_for_game_test"
        and not blocking
        and verification.get("ok")
        and installed.get("matches_package")
        and not proof_state.get("game_tested")
    )
    next_action = "No action required; this package is recorded as game-tested."
    if not verification.get("ok") or blocking:
        next_action = "Fix blocking package/install issues before launching KOTOR."
    elif proof_state.get("game_tested") and not proof_state.get("missing_checks"):
        next_action = "No action required; this package is recorded as game-tested."
    elif ready_for_game_launch:
        game_label = "KOTOR II" if launch_handoff.get("game") == "K2" else "KOTOR"
        next_action = (
            f"Launch {game_label}, run `{launch_handoff['warp_command']}`, verify floor/placeable/walkability, "
            "then capture evidence and run the proof recording command."
        )
        if launch_handoff.get("evidence_capture_command"):
            next_action = (
                f"Launch {game_label}, run `{launch_handoff['warp_command']}`, verify floor/placeable/walkability, "
                "then run the evidence capture command."
            )
    elif not installed.get("checked") or not installed.get("exists"):
        next_action = "Install/copy grdev01.mod into a KOTOR Modules folder before the game test."
    elif installed.get("checked") and not installed.get("matches_package"):
        next_action = "Reinstall the staged grdev01.mod so the live Modules copy matches the verified package."
    return {
        "ok": complete,
        "status": status if not blocking else ("game_tested" if complete else status),
        "proof_manifest_path": str(proof_manifest),
        "module_path": str(checked_module_path),
        "pack_manifest_path": str(package.get("pack_manifest_path") or ""),
        "package_verification": verification,
        "runtime_archive": runtime_archive,
        "proof": proof_state,
        "installed": installed,
        "kotormcp": kotormcp,
        "launch_handoff": launch_handoff,
        "ready_for_game_launch": ready_for_game_launch,
        "next_action": next_action,
        "warnings": warnings,
        "blocking_issues": blocking,
    }


def _print_human_summary(status: dict[str, Any]) -> None:
    print(f"grdev01 smoke status: {status['status']}")
    print(f"Module package: {status['module_path']}")
    print(f"Proof manifest: {status['proof_manifest_path']}")
    if status["pack_manifest_path"]:
        print(f"Pack manifest: {status['pack_manifest_path']}")
    print(f"Package readback: {status['package_verification']['code']}")
    print(f"Engine module IFO key: {status['runtime_archive']['engine_ifo_key_ok']}")
    installed = status["installed"]
    if installed["checked"]:
        print(f"Installed copy: {installed['installed_module_path']}")
        print(f"Installed copy matches package: {installed['matches_package']}")
        if installed["backup_module_path"]:
            print(f"Previous module backup: {installed['backup_module_path']}")
    kotormcp = status.get("kotormcp") or {}
    if kotormcp.get("checked"):
        print(f"KotorMCP module check: {kotormcp['ok']} ({kotormcp['resource_count']} resource(s))")
        if kotormcp.get("model_buffer_entry_type"):
            print(f"KotorMCP model buffer entry type: {kotormcp['model_buffer_entry_type']}")
    print(f"Ready for game launch: {status['ready_for_game_launch']}")
    handoff = status.get("launch_handoff") or {}
    if handoff.get("game"):
        print(f"Game: {handoff['game']}")
    if handoff.get("launch_helper_command"):
        print(f"Launch helper: {handoff['launch_helper_command']}")
    if handoff.get("elevated_launch_script_path"):
        print(f"Elevated launch script: {handoff['elevated_launch_script_path']}")
    if handoff.get("evidence_capture_command"):
        print(f"Evidence capture command: {handoff['evidence_capture_command']}")
    if handoff.get("proof_recording_script_path"):
        print(f"Proof recorder script: {handoff['proof_recording_script_path']}")
    if handoff.get("proof_recording_command_template"):
        print(f"Proof recorder command: {handoff['proof_recording_command_template']}")
    print(f"Next action: {status['next_action']}")
    proof = status["proof"]
    print(f"Game-tested: {proof['game_tested']}")
    print(f"Manual proof required: {proof['manual_proof_required']}")
    if proof["evidence_path"]:
        print(f"Evidence: {proof['evidence_path']} (exists: {proof['evidence_exists']})")
    if proof["missing_checks"]:
        print("")
        print("Missing proof checks:")
        for check in proof["missing_checks"]:
            print(f"- {check}")
    if status["warnings"]:
        print("")
        print("Warnings:")
        for warning in status["warnings"]:
            print(f"- {warning}")
    if kotormcp.get("warnings"):
        print("")
        print("KotorMCP warnings:")
        for warning in kotormcp["warnings"]:
            print(f"- {warning}")
    if status["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in status["blocking_issues"]:
            print(f"- {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    status = build_status(
        proof_manifest=args.proof_manifest,
        module_path=args.module_path,
        game_modules_dir=args.game_modules_dir,
        use_kotormcp=args.kotormcp,
    )
    if args.json:
        print(json.dumps(status, indent=2))
    else:
        _print_human_summary(status)
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
