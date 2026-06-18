"""Launch KOTOR for the installed grdev01 Map Studio smoke test.

This helper checks the proof manifest, verifies the staged package, verifies the
installed Modules copy matches the package, then launches `swkotor.exe`.
It does not mark proof complete; use `record_authored_module_game_proof.py`
after capturing real evidence from `warp grdev01`.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROOF_MANIFEST = ROOT / "artifacts" / "map_studio" / "grdev01_authored_smoke_installed" / "grdev01_authored_module_game_manifest.json"
DEFAULT_K1_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")


def _load_status_module() -> Any:
    script = ROOT / "scripts" / "check_grdev01_smoke_status.py"
    spec = importlib.util.spec_from_file_location("ghostrigger_check_grdev01_smoke_status", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load status helper from {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--proof-manifest",
        type=Path,
        default=DEFAULT_PROOF_MANIFEST,
        help="Proof manifest written by the authored smoke prep command.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=DEFAULT_K1_ROOT,
        help="KOTOR install root containing swkotor.exe and Modules.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional explicit Modules folder. Defaults to <game-root-dir>/Modules.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify readiness and print the launch command without starting KOTOR.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Launch even if status says the package is not ready. This is for diagnostics only.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _proof_recording_script_path(proof_manifest: Path) -> str:
    try:
        proof = json.loads(proof_manifest.read_text(encoding="utf-8"))
    except Exception:
        return ""
    handoff = proof.get("launch_handoff") if isinstance(proof, dict) else {}
    if not isinstance(handoff, dict):
        return ""
    return str(handoff.get("proof_recording_script_path") or "")


def _summary(
    *,
    ok: bool,
    code: str,
    message: str,
    status: dict[str, Any],
    executable: Path,
    launch_command: list[str],
    proof_recording_script_path: str,
    dry_run: bool,
) -> dict[str, Any]:
    next_action = str(status.get("next_action", "") or "")
    if ok:
        next_action = "In KOTOR, open the console and run `warp grdev01`. Then capture evidence and record proof."
        if proof_recording_script_path:
            next_action += f" Run `{proof_recording_script_path}` after capturing screenshot/video evidence."
    return {
        "ok": ok,
        "code": code,
        "message": message,
        "status": status.get("status", ""),
        "ready_for_game_launch": bool(status.get("ready_for_game_launch", False)),
        "proof_manifest_path": status.get("proof_manifest_path", ""),
        "module_path": status.get("module_path", ""),
        "installed_module_path": (status.get("installed") or {}).get("installed_module_path", ""),
        "installed_matches_package": bool((status.get("installed") or {}).get("matches_package", False)),
        "executable_path": str(executable),
        "launch_command": launch_command,
        "proof_recording_script_path": proof_recording_script_path,
        "dry_run": dry_run,
        "next_action": next_action,
        "warnings": list(status.get("warnings", [])),
        "blocking_issues": list(status.get("blocking_issues", [])),
    }


def _print_human_summary(payload: dict[str, Any]) -> None:
    result = "OK" if payload["ok"] else "BLOCKED"
    print(f"grdev01 KOTOR launch: {result} ({payload['code']})")
    print(payload["message"])
    print(f"Status: {payload['status']}")
    print(f"Proof manifest: {payload['proof_manifest_path']}")
    print(f"Module package: {payload['module_path']}")
    print(f"Installed module: {payload['installed_module_path']}")
    print(f"Installed copy matches package: {payload['installed_matches_package']}")
    print(f"Executable: {payload['executable_path']}")
    print(f"Command: {' '.join(payload['launch_command'])}")
    if payload.get("proof_recording_script_path"):
        print(f"Proof recorder: {payload['proof_recording_script_path']}")
    if payload["dry_run"]:
        print("Dry run: KOTOR was not launched.")
    if payload["next_action"]:
        print(f"Next action: {payload['next_action']}")
    if payload["warnings"]:
        print("")
        print("Warnings:")
        for warning in payload["warnings"]:
            print(f"- {warning}")
    if payload["blocking_issues"]:
        print("")
        print("Blocking issues:")
        for issue in payload["blocking_issues"]:
            print(f"- {issue}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    modules_dir = args.game_modules_dir or args.game_root_dir / "Modules"
    executable = args.game_root_dir / "swkotor.exe"
    status_module = _load_status_module()
    status = status_module.build_status(proof_manifest=args.proof_manifest, game_modules_dir=modules_dir)
    launch_command = [str(executable)]
    proof_recorder = _proof_recording_script_path(args.proof_manifest)
    blocking = list(status.get("blocking_issues", []))
    if not executable.is_file():
        blocking.append(f"KOTOR executable does not exist: {executable}")
    ready = bool(status.get("ready_for_game_launch", False)) and not blocking
    if not ready and not args.force:
        status = dict(status)
        status["blocking_issues"] = blocking
        payload = _summary(
            ok=False,
            code="not_ready",
            message="KOTOR was not launched because the grdev01 smoke package is not ready.",
            status=status,
            executable=executable,
            launch_command=launch_command,
            proof_recording_script_path=proof_recorder,
            dry_run=bool(args.dry_run),
        )
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            _print_human_summary(payload)
        return 1
    if not args.dry_run:
        try:
            subprocess.Popen(launch_command, cwd=str(args.game_root_dir))  # noqa: S603
        except OSError as exc:
            status = dict(status)
            blocking = list(status.get("blocking_issues", []))
            winerror = getattr(exc, "winerror", None) or getattr(exc, "errno", None)
            if winerror == 740:
                code = "launch_requires_elevation"
                message = "KOTOR was not launched because Windows requires elevation for this executable."
                blocking.append(
                    f"Windows requires elevation to launch {executable}. Start KOTOR as administrator, then run `warp grdev01`."
                )
            else:
                code = "launch_failed"
                message = f"KOTOR launch failed: {exc}"
                blocking.append(message)
            status["blocking_issues"] = blocking
            payload = _summary(
                ok=False,
                code=code,
                message=message,
                status=status,
                executable=executable,
                launch_command=launch_command,
                proof_recording_script_path=proof_recorder,
                dry_run=False,
            )
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                _print_human_summary(payload)
            return 1
    payload = _summary(
        ok=True,
        code="dry_run_ready" if args.dry_run else "launched",
        message=(
            "Dry run passed; KOTOR launch command is ready."
            if args.dry_run
            else "KOTOR launched for grdev01 smoke testing."
        ),
        status=status,
        executable=executable,
        launch_command=launch_command,
        proof_recording_script_path=proof_recorder,
        dry_run=bool(args.dry_run),
    )
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_human_summary(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
