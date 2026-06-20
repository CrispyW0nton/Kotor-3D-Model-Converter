"""Stage byte-for-byte stock KOTOR module filename diagnostics.

This is the narrowest crash-isolation fixture in the grdev01 Map Studio smoke
chain.  It copies the stock `tar_m02aa.rim` bytes directly to a staged
`grdev01.mod` filename and a staged `grdev01.rim` filename without rebuilding
the archive, rewriting resources, or changing any internal roots.  It also
copies the stock `tar_m02aa_s.rim` sidecar as `grdev01_s.rim` for the closest
native RIM-pair diagnostic.

Use it only to answer one question:

* If the GhostRigger-built stock-area MOD crashes but the exact stock RIM bytes
  load under either custom filename, investigate GhostRigger MOD packaging.
* If exact stock bytes fail under both custom filenames, investigate KOTOR's
  module filename/root handoff behavior before generated geometry or WOK data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_MODULE_ROOT = "grdev01"
STOCK_MODULE_ROOT = "m02aa"
STOCK_RIM = "tar_m02aa.rim"
STOCK_STATIC_RIM = "tar_m02aa_s.rim"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "artifacts" / "map_studio" / "grdev01_exact_stock_module_rename",
        help="Directory that receives the staged exact stock module rename.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        help="KOTOR install root used to read stock tar_m02aa.rim.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder. Omit this to only stage the diagnostic package.",
    )
    parser.add_argument("--install", action="store_true", help="Copy the staged grdev01.mod bytes to <Modules>/grdev01.mod.")
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Back up and replace an existing grdev01.mod when --install is used.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _header(path: Path) -> str:
    data = path.read_bytes()[:16]
    return data.decode("ascii", errors="replace").rstrip("\x00")


def _next_backup_path(path: Path) -> Path:
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _install_module(module_path: Path, modules_dir: Path, *, overwrite: bool) -> tuple[str, str, list[str], list[str]]:
    warnings: list[str] = []
    blocking: list[str] = []
    modules_dir.mkdir(parents=True, exist_ok=True)
    destination = modules_dir / "grdev01.mod"
    backup_path = ""
    if destination.exists():
        if not overwrite:
            blocking.append(f"{destination} already exists. Re-run with --overwrite-module to replace it.")
            return "", "", warnings, blocking
        backup = _next_backup_path(destination)
        shutil.copy2(destination, backup)
        backup_path = str(backup)
        warnings.append(f"Backed up existing {destination.name} to {backup}.")
    shutil.copy2(module_path, destination)
    return str(destination), backup_path, warnings, blocking


def _manifest(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "grdev01_exact_stock_module_rename",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "package_module_root": PACKAGE_MODULE_ROOT,
        "stock_module_root": STOCK_MODULE_ROOT,
        "source_module": STOCK_RIM,
        "archive_mode": "byte_for_byte_stock_rim_and_static_sidecar_custom_module_filenames",
        "diagnostic_question": (
            "If this exact renamed stock RIM loads but the GhostRigger-built stock-area MOD crashes, "
            "investigate GhostRigger MOD packaging. If this also crashes, investigate the KOTOR "
            "filename/root handoff for custom warp targets before generated room geometry."
        ),
        "summary": summary,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 exact stock module rename: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Package: {summary['module_path'] or '(not written)'}")
    if summary.get("rim_path"):
        print(f"RIM package: {summary['rim_path']}")
    if summary.get("static_rim_path"):
        print(f"Static RIM sidecar: {summary['static_rim_path']}")
    print(f"Manifest: {summary['manifest_path'] or '(not written)'}")
    if summary["installed_module_path"]:
        print(f"Installed module: {summary['installed_module_path']}")
    elif summary["module_path"]:
        print("Not installed; current game grdev01.mod was intentionally left untouched.")
    if summary["backup_module_path"]:
        print(f"Backup: {summary['backup_module_path']}")
    if summary["warnings"]:
        print("\nWarnings:")
        for warning in summary["warnings"]:
            print(f"- {warning}")
    if summary["blocking_issues"]:
        print("\nBlocking issues:")
        for issue in summary["blocking_issues"]:
            print(f"- {issue}")
    print("\nNext actions:")
    for action in summary["next_actions"]:
        print(f"- {action}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    output_dir = args.output_dir
    module_dir = output_dir / "install" / "Modules"
    module_path = module_dir / "grdev01.mod"
    rim_path = module_dir / "grdev01.rim"
    static_rim_path = module_dir / "grdev01_s.rim"
    stock_path = args.game_root_dir / "Modules" / STOCK_RIM
    stock_static_path = args.game_root_dir / "Modules" / STOCK_STATIC_RIM
    warnings: list[str] = []
    blocking: list[str] = []
    installed_path = ""
    backup_path = ""
    stock_hash = ""
    staged_hash = ""
    stock_static_hash = ""
    staged_static_hash = ""
    stock_header = ""
    staged_header = ""
    stock_static_header = ""
    staged_static_header = ""

    try:
        if not stock_path.exists():
            blocking.append(f"Stock module not found: {stock_path}")
        if not stock_static_path.exists():
            blocking.append(f"Stock static module sidecar not found: {stock_static_path}")
        if not blocking:
            module_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stock_path, module_path)
            shutil.copy2(stock_path, rim_path)
            shutil.copy2(stock_static_path, static_rim_path)
            stock_hash = _sha256(stock_path)
            staged_hash = _sha256(module_path)
            stock_static_hash = _sha256(stock_static_path)
            staged_static_hash = _sha256(static_rim_path)
            stock_header = _header(stock_path)
            staged_header = _header(module_path)
            stock_static_header = _header(stock_static_path)
            staged_static_header = _header(static_rim_path)
            if stock_hash != staged_hash:
                blocking.append("Staged grdev01.mod bytes do not match stock tar_m02aa.rim bytes.")
            if _sha256(rim_path) != stock_hash:
                blocking.append("Staged grdev01.rim bytes do not match stock tar_m02aa.rim bytes.")
            if staged_static_hash != stock_static_hash:
                blocking.append("Staged grdev01_s.rim bytes do not match stock tar_m02aa_s.rim bytes.")
            if args.install:
                if not args.game_modules_dir:
                    blocking.append("--install requires --game-modules-dir.")
                elif not blocking:
                    installed_path, backup_path, install_warnings, install_blocking = _install_module(
                        module_path,
                        args.game_modules_dir,
                        overwrite=bool(args.overwrite_module),
                    )
                    warnings.extend(install_warnings)
                    blocking.extend(install_blocking)
    except Exception as exc:
        blocking.append(f"Exact stock module rename failed: {exc}")

    ok = not blocking
    message = (
        "Exact stock module rename diagnostic is installed for in-game warp testing."
        if ok and installed_path
        else "Exact stock module rename diagnostic is staged."
        if ok
        else "Exact stock module rename diagnostic is not ready; resolve blocking issues first."
    )
    next_actions = (
        [
            "Launch KOTOR and run `warp grdev01` with this exact renamed stock RIM installed.",
            "If it loads, compare against the GhostRigger-built stock-area MOD to isolate archive writer differences.",
            "If it crashes, investigate module filename/root lookup before generated room geometry.",
        ]
        if installed_path
        else [
            "Keep the currently installed diagnostic active until that `warp grdev01` result is known.",
            "If the GhostRigger-built stock-area MOD crashes, install this exact renamed stock RIM and test `warp grdev01` again.",
        ]
    )
    summary = {
        "ok": ok,
        "code": "prepared" if ok else "blocked",
        "message": message,
        "output_dir": str(output_dir),
        "game_root_dir": str(args.game_root_dir),
        "source_module_path": str(stock_path),
        "module_path": str(module_path) if module_path.exists() else "",
        "rim_path": str(rim_path) if rim_path.exists() else "",
        "static_rim_path": str(static_rim_path) if static_rim_path.exists() else "",
        "installed_module_path": installed_path,
        "backup_module_path": backup_path,
        "manifest_path": str(output_dir / "grdev01_exact_stock_module_rename_manifest.json"),
        "source_sha256": stock_hash,
        "staged_sha256": staged_hash,
        "source_static_sha256": stock_static_hash,
        "staged_static_sha256": staged_static_hash,
        "source_header": stock_header,
        "staged_header": staged_header,
        "source_static_header": stock_static_header,
        "staged_static_header": staged_static_header,
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": next_actions,
    }
    manifest_path = output_dir / "grdev01_exact_stock_module_rename_manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(_manifest(summary), indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
