"""Stage a grdev01 diagnostic package from a nearly stock KOTOR area.

This is a stronger crash-isolation fixture than the stock-room shell.  It
packages the stock `tar_m02aa` module resources as `grdev01.mod` while keeping
the stock internal area/resource roots (`m02aa`, `module.ifo`, and all room
assets).  The package is staged by default so it does not replace the active
`grdev01` test installed in KOTOR's Modules folder.

Use it if the stock-room shell still crashes:

* If this stock-area clone loads, generated `grdev01` metadata is suspect.
* If this stock-area clone crashes, the issue is probably package/load-path
  related rather than room geometry or authored metadata.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
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
    ".",
)

PACKAGE_MODULE_ROOT = "grdev01"
STOCK_MODULE_ROOT = "m02aa"
STOCK_RIM = "tar_m02aa.rim"


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
        default=ROOT / "artifacts" / "map_studio" / "grdev01_stock_area_clone",
        help="Directory that receives the staged stock-area clone package.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        help="KOTOR install root used to read stock tar_m02aa resources.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder. Omit this to only stage the diagnostic package.",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="Actually copy the staged package to <Modules>/grdev01.mod. By default this script only stages.",
    )
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Back up and replace an existing grdev01.mod when --install is used.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _resource_bytes(result: Any, label: str) -> bytes:
    data = getattr(result, "data", result)
    if callable(data):
        data = data()
    data = bytes(data or b"")
    if not data:
        raise ValueError(f"Stock resource {label} has no bytes.")
    return data


def _installation_resource(installation: Any, resref: str, restype: Any) -> bytes:
    result = installation.resource(resref, restype)
    if result is None:
        raise FileNotFoundError(f"Could not find stock resource {resref}.{restype.extension}.")
    return _resource_bytes(result, f"{resref}.{restype.extension}")


def _rim_resource(rim: Any, resref: str, restype: Any) -> bytes:
    data = rim.get(resref, restype)
    if not data:
        raise FileNotFoundError(f"Could not find stock RIM resource {resref}.{restype.extension}.")
    return bytes(data)


def _stock_rooms_from_lyt(lyt_bytes: bytes) -> list[str]:
    rooms: list[str] = []
    remaining = 0
    for line in lyt_bytes.decode("latin-1", errors="replace").splitlines():
        tokens = line.strip().split()
        if not tokens:
            continue
        keyword = tokens[0].lower()
        if keyword == "roomcount":
            remaining = int(tokens[1]) if len(tokens) > 1 else 0
            continue
        if remaining > 0 and len(tokens) >= 4:
            rooms.append(tokens[0].lower())
            remaining -= 1
    return rooms


def _load_stock_module_resources(game_root_dir: Path) -> tuple[list[Any], list[str]]:
    from pykotor.extract.installation import Installation
    from pykotor.resource.formats.rim.rim_auto import read_rim
    from pykotor.resource.type import ResourceType
    from src.core.modules.custom_module_packager import PackagedModuleResource

    installation = Installation(str(game_root_dir))
    rim = read_rim(game_root_dir / "Modules" / STOCK_RIM)
    lyt = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.LYT)
    vis = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.VIS)
    pth = _installation_resource(installation, STOCK_MODULE_ROOT, ResourceType.PTH)
    rooms = _stock_rooms_from_lyt(lyt)
    resources = [
        PackagedModuleResource(STOCK_MODULE_ROOT, "are", _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.ARE), source=f"stock:{STOCK_RIM}"),
        PackagedModuleResource(STOCK_MODULE_ROOT, "git", _rim_resource(rim, STOCK_MODULE_ROOT, ResourceType.GIT), source=f"stock:{STOCK_RIM}"),
        PackagedModuleResource("module", "ifo", _rim_resource(rim, "module", ResourceType.IFO), source=f"stock:{STOCK_RIM}"),
        PackagedModuleResource(STOCK_MODULE_ROOT, "lyt", lyt, source="stock:bif"),
        PackagedModuleResource(STOCK_MODULE_ROOT, "vis", vis, source="stock:bif"),
        PackagedModuleResource(STOCK_MODULE_ROOT, "pth", pth, source="stock:bif"),
    ]
    for room in rooms:
        resources.extend(
            [
                PackagedModuleResource(room, "mdl", _installation_resource(installation, room, ResourceType.MDL), source="stock:bif"),
                PackagedModuleResource(room, "mdx", _installation_resource(installation, room, ResourceType.MDX), source="stock:bif"),
                PackagedModuleResource(room, "wok", _installation_resource(installation, room, ResourceType.WOK), source="stock:bif"),
            ]
        )
    return resources, rooms


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


def _readback(module_path: str) -> dict[str, Any]:
    from pykotor.resource.formats.erf.erf_auto import read_erf

    path = Path(module_path)
    erf = read_erf(path)
    resources = []
    for item in erf:
        data = erf.get(item.resref, item.restype) or b""
        resources.append(
            {
                "resref": item.resref,
                "restype": item.restype.extension,
                "type_id": item.restype.type_id,
                "size": len(data),
            }
        )
    return {
        "path": str(path),
        "size": path.stat().st_size if path.exists() else 0,
        "resource_count": len(resources),
        "resources": sorted(resources, key=lambda item: (item["resref"], item["restype"])),
    }


def _manifest(summary: dict[str, Any], rooms: list[str], readback: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "grdev01_stock_area_clone",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "package_module_root": PACKAGE_MODULE_ROOT,
        "stock_module_root": STOCK_MODULE_ROOT,
        "source_module": STOCK_RIM,
        "stock_rooms": rooms,
        "diagnostic_question": (
            "If this staged package loads after installing it as grdev01.mod, the grdev01 authored metadata/generation path is suspect. "
            "If it also crashes, investigate MOD packaging or KOTOR's expectations when a renamed module package points at stock area resources."
        ),
        "summary": summary,
        "readback": readback,
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 stock-area clone: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Package: {summary['module_path'] or '(not written)'}")
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
    _install_payload_paths()

    from src.core.modules.custom_module_packager import CustomModulePackRequest, package_custom_module

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    blocking: list[str] = []
    rooms: list[str] = []
    readback: dict[str, Any] = {}
    installed_path = ""
    backup_path = ""
    try:
        resources, rooms = _load_stock_module_resources(args.game_root_dir)
        package_result = package_custom_module(
            SimpleNamespace(resources={}),
            CustomModulePackRequest(
                module_root=PACKAGE_MODULE_ROOT,
                game="K1",
                output_dir=str(output_dir),
                archive_mode="mod",
                create_backups=True,
                write_loose_resources=True,
                include_reference_check=False,
                include_wok_check=False,
                strict=True,
            ),
            resources=resources,
        )
        warnings.extend(package_result.warnings)
        blocking.extend(package_result.blocking_issues)
        if package_result.module_path:
            readback = _readback(package_result.module_path)
        if package_result.ok and not blocking and args.install:
            if not args.game_modules_dir:
                blocking.append("--install requires --game-modules-dir.")
            else:
                installed_path, backup_path, install_warnings, install_blocking = _install_module(
                    Path(package_result.module_path),
                    args.game_modules_dir,
                    overwrite=bool(args.overwrite_module),
                )
                warnings.extend(install_warnings)
                blocking.extend(install_blocking)
        ok = bool(package_result.ok) and not blocking
        module_path = package_result.module_path
    except Exception as exc:
        ok = False
        module_path = ""
        blocking.append(f"Stock-area clone package failed: {exc}")

    code = "prepared" if ok else "blocked"
    message = (
        "Stock-area clone diagnostic package is staged."
        if ok and not installed_path
        else "Stock-area clone diagnostic package is installed for in-game warp testing."
        if ok
        else "Stock-area clone diagnostic package is not ready; resolve blocking issues first."
    )
    if installed_path:
        next_actions = [
            "Launch KOTOR and run `warp grdev01` with this installed full stock-area clone.",
            "If this stock-area clone loads, investigate the generated grdev01 metadata/room-shell path next.",
            "If this stock-area clone crashes, investigate MOD package/load-path behavior before editing generated room geometry again.",
        ]
    else:
        next_actions = [
            "Keep the currently installed diagnostic active until that `warp grdev01` result is known.",
            "If that package still crashes, install this staged stock-area clone and test `warp grdev01` again.",
            "Use the outcome to decide whether to fix generated room assets, generated metadata, or MOD packaging/load-path behavior.",
        ]
    summary = {
        "ok": ok,
        "code": code,
        "message": message,
        "output_dir": str(output_dir),
        "game_root_dir": str(args.game_root_dir),
        "module_path": module_path,
        "installed_module_path": installed_path,
        "backup_module_path": backup_path,
        "manifest_path": str(output_dir / "grdev01_stock_area_clone_manifest.json"),
        "stock_room_count": len(rooms),
        "resource_count": int(readback.get("resource_count") or 0),
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": next_actions,
    }
    manifest_path = output_dir / "grdev01_stock_area_clone_manifest.json"
    manifest_path.write_text(json.dumps(_manifest(summary, rooms, readback), indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
