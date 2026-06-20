"""Prepare a grdev01 crash-isolation module using a stock KOTOR room shell.

This diagnostic package keeps GhostRigger's generated module shell
(`grdev01.are`, `grdev01.git`, `module.ifo`, `grdev01.lyt`, `grdev01.vis`,
`grdev01.pth`) but swaps the generated room MDL/MDX/WOK for BioWare's stock
`m02aa_03a` room assets.

Use this only to isolate whether a `warp grdev01` crash is caused by the
generated room model/walkmesh or by the module metadata/container itself.
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

MODULE_ROOT = "grdev01"
STOCK_AREA_ROOT = "m02aa"
STOCK_ROOM_RESREF = "m02aa_03a"
STOCK_ROOM_LYT_POSITION = (75.0, 150.0, 0.0)
STOCK_ROOM_ENTRY_POSITION = (91.95486450195312, 132.73565673828125, 0.0)
STOCK_ROOM_ENTRY_FACING = -0.7853978872299194


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
        default=ROOT / "artifacts" / "map_studio" / "grdev01_stock_room_shell",
        help="Directory that receives the diagnostic package and manifest.",
    )
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor"),
        help="KOTOR install root used to pull stock m02aa_03a resources.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Optional KOTOR Modules folder to copy grdev01.mod into.",
    )
    parser.add_argument(
        "--overwrite-module",
        action="store_true",
        help="Back up and replace an existing grdev01.mod in the target Modules folder.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build and verify the diagnostic package without copying it into Modules.",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary.")
    return parser


def _resource_bytes(installation: Any, resref: str, restype: Any) -> bytes:
    result = installation.resource(resref, restype)
    if result is None:
        raise FileNotFoundError(f"Could not find stock resource {resref}.{restype.extension}.")
    data = getattr(result, "data", result)
    if callable(data):
        data = data()
    data = bytes(data or b"")
    if not data:
        raise ValueError(f"Stock resource {resref}.{restype.extension} has no bytes.")
    return data


def _load_stock_room_resources(game_root_dir: Path) -> dict[tuple[str, str], bytes]:
    from pykotor.extract.installation import Installation
    from pykotor.resource.type import ResourceType

    installation = Installation(str(game_root_dir))
    return {
        (STOCK_ROOM_RESREF, "mdl"): _resource_bytes(installation, STOCK_ROOM_RESREF, ResourceType.MDL),
        (STOCK_ROOM_RESREF, "mdx"): _resource_bytes(installation, STOCK_ROOM_RESREF, ResourceType.MDX),
        (STOCK_ROOM_RESREF, "wok"): _resource_bytes(installation, STOCK_ROOM_RESREF, ResourceType.WOK),
    }


def _build_pth_bytes() -> bytes:
    from pykotor.resource.generics.pth import PTH, bytes_pth

    pth = PTH()
    point_a = pth.add(STOCK_ROOM_ENTRY_POSITION[0], STOCK_ROOM_ENTRY_POSITION[1])
    point_b = pth.add(STOCK_ROOM_ENTRY_POSITION[0] - 0.75, STOCK_ROOM_ENTRY_POSITION[1] + 0.25)
    pth.connect(point_a, point_b)
    pth.connect(point_b, point_a)
    return bytes_pth(pth)


def _build_module_resources(stock_resources: dict[tuple[str, str], bytes]) -> list[Any]:
    from src.core.modules.authored_module_metadata import AuthoredAreaMetadata, build_authored_are_bytes, build_authored_ifo_bytes
    from src.core.modules.authored_module_objects import AuthoredGameplayPlacement, ModuleEntryPoint, build_git_bytes
    from src.core.modules.authored_module_project import AuthoredModuleMetadata
    from src.core.modules.custom_module_packager import PackagedModuleResource
    from src.core.modules.module_format import LYTLayout, LYTRoom, VISData

    module = AuthoredModuleMetadata(
        module_root=MODULE_ROOT,
        game="K1",
        display_name="GhostRigger Stock Room Shell",
        tag=MODULE_ROOT,
        description="Crash-isolation module using stock m02aa_03a room assets.",
        metadata={"diagnostic": "stock_room_shell", "stock_area": STOCK_AREA_ROOT},
    )
    area = AuthoredAreaMetadata(
        name="GhostRigger Stock Room Shell",
        tag=MODULE_ROOT,
        comments="Crash-isolation package. Room assets are stock KOTOR m02aa_03a.",
        unescapable=True,
    )
    entry = ModuleEntryPoint(area_resref=MODULE_ROOT, position=STOCK_ROOM_ENTRY_POSITION, facing=STOCK_ROOM_ENTRY_FACING)
    lyt = LYTLayout(
        rooms=[
            LYTRoom(
                STOCK_ROOM_RESREF,
                STOCK_ROOM_LYT_POSITION[0],
                STOCK_ROOM_LYT_POSITION[1],
                STOCK_ROOM_LYT_POSITION[2],
            )
        ]
    )
    vis = VISData(visibility={STOCK_ROOM_RESREF: [STOCK_ROOM_RESREF]})
    resources = [
        PackagedModuleResource(MODULE_ROOT, "are", build_authored_are_bytes(module, area, room_resrefs=(STOCK_ROOM_RESREF,)), source="diagnostic:generated_are"),
        PackagedModuleResource(MODULE_ROOT, "git", build_git_bytes(AuthoredGameplayPlacement(entry_point=entry)), source="diagnostic:generated_git"),
        PackagedModuleResource("module", "ifo", build_authored_ifo_bytes(module, entry, area_resrefs=(MODULE_ROOT,)), source="diagnostic:generated_ifo"),
        PackagedModuleResource(MODULE_ROOT, "lyt", lyt.to_text().encode("latin-1"), source="diagnostic:generated_lyt"),
        PackagedModuleResource(MODULE_ROOT, "vis", vis.to_text().encode("latin-1"), source="diagnostic:generated_vis"),
        PackagedModuleResource(MODULE_ROOT, "pth", _build_pth_bytes(), source="diagnostic:generated_pth"),
    ]
    for (resref, restype), data in sorted(stock_resources.items()):
        resources.append(PackagedModuleResource(resref, restype, data, source=f"stock:{STOCK_AREA_ROOT}"))
    return resources


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
        "kind": "grdev01_stock_room_shell",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "module_root": MODULE_ROOT,
        "game": "K1",
        "stock_room": {
            "area": STOCK_AREA_ROOT,
            "room_resref": STOCK_ROOM_RESREF,
            "lyt_position": list(STOCK_ROOM_LYT_POSITION),
            "entry_position": list(STOCK_ROOM_ENTRY_POSITION),
            "entry_facing": STOCK_ROOM_ENTRY_FACING,
        },
        "diagnostic_question": (
            "If warp grdev01 loads here, the previous crash is likely in GhostRigger's generated room MDL/WOK. "
            "If it still crashes, the issue is likely in the grdev01 module shell/container metadata."
        ),
        "summary": summary,
        "acceptance_checks": [
            "module_loads_in_game",
            "player_spawns_on_floor",
            "player_can_walk_on_floor",
        ],
    }


def _print_human_summary(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 stock-room shell: {status} ({summary['code']})")
    print(summary["message"])
    print(f"Package: {summary['module_path'] or '(not written)'}")
    print(f"Manifest: {summary['manifest_path'] or '(not written)'}")
    if summary.get("installed_module_path"):
        print(f"Installed module: {summary['installed_module_path']}")
    if summary.get("backup_module_path"):
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
    from src.core.modules.dev_module_smoke import verify_dev_test_module_package

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    blocking: list[str] = []
    try:
        stock_resources = _load_stock_room_resources(args.game_root_dir)
        resources = _build_module_resources(stock_resources)
        package_result = package_custom_module(
            SimpleNamespace(resources={}),
            CustomModulePackRequest(
                module_root=MODULE_ROOT,
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
        verification = verify_dev_test_module_package(
            package_result.module_path,
            expected_module_root=MODULE_ROOT,
            expected_room_resref=STOCK_ROOM_RESREF,
        )
        warnings.extend(item for item in verification.warnings if item not in warnings)
        blocking.extend(item for item in verification.blocking_issues if item not in blocking)
        installed_path = ""
        backup_path = ""
        if package_result.ok and not blocking and args.game_modules_dir and not args.dry_run:
            installed_path, backup_path, install_warnings, install_blocking = _install_module(
                Path(package_result.module_path),
                args.game_modules_dir,
                overwrite=bool(args.overwrite_module),
            )
            warnings.extend(install_warnings)
            blocking.extend(install_blocking)
        ok = bool(package_result.ok) and not blocking and (bool(installed_path) or bool(args.dry_run) or not args.game_modules_dir)
        code = "prepared" if ok else "blocked"
        message = (
            "Stock-room diagnostic package is ready for in-game warp testing."
            if ok
            else "Stock-room diagnostic package is not ready; resolve blocking issues first."
        )
        module_path = package_result.module_path
    except Exception as exc:
        ok = False
        code = "exception"
        message = f"Stock-room diagnostic package failed: {exc}"
        module_path = ""
        installed_path = ""
        backup_path = ""
        blocking.append(message)

    summary = {
        "ok": ok,
        "code": code,
        "message": message,
        "output_dir": str(output_dir),
        "game_root_dir": str(args.game_root_dir),
        "module_path": module_path,
        "installed_module_path": installed_path,
        "backup_module_path": backup_path,
        "manifest_path": str(output_dir / "grdev01_stock_room_shell_manifest.json"),
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": [
            "Launch KOTOR and run `warp grdev01`.",
            "Confirm whether the stock Taris room loads, the player spawns on the floor, and walking works.",
            "If this loads, focus the next fix on generated room MDL/WOK output. If it crashes, focus on ARE/GIT/IFO/LYT/VIS/PTH/package metadata.",
        ],
    }
    manifest_path = output_dir / "grdev01_stock_room_shell_manifest.json"
    manifest_path.write_text(json.dumps(_manifest(summary), indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human_summary(summary)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
