"""Install one known grdev01 runtime diagnostic variant.

This is a guarded copier for the crash-isolation ladder.  It only installs
known staged grdev01 packages and records exactly which variant became active.
It does not mark the module game-tested; that still requires a real KOTOR
`warp grdev01` proof pass.
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
DEFAULT_GAME_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
DEFAULT_OUTPUT_ROOT = ROOT / "artifacts" / "map_studio" / "grdev01_runtime_installs"


VARIANTS: dict[str, dict[str, str]] = {
    "stock-mod": {
        "id": "ghostrigger_stock_area_mod",
        "label": "GhostRigger-built stock-area MOD baseline",
        "relative_path": "artifacts/map_studio/grdev01_stock_area_clone_runtime_baseline/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a GhostRigger-built MOD archive containing stock m02aa roots and rooms?",
    },
    "exact-rim": {
        "id": "exact_stock_rim_rename",
        "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.mod",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim",
        "expected_header": "RIM V1.0",
        "proof_question": "Can KOTOR load stock RIM bytes through the custom grdev01 filename?",
    },
    "exact-rim-file": {
        "id": "exact_stock_rim_custom_filename",
        "label": "Byte-for-byte stock tar_m02aa RIM renamed to grdev01.rim",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.rim",
        "destination_name": "grdev01.rim",
        "conflicting_destination_names": "grdev01.mod,grdev01_s.rim",
        "expected_header": "RIM V1.0",
        "proof_question": "Can KOTOR load stock RIM bytes through a custom grdev01.rim filename when no grdev01.mod is present?",
    },
    "exact-rim-pair": {
        "id": "exact_stock_rim_pair",
        "label": "Byte-for-byte stock tar_m02aa RIM pair renamed to grdev01.rim and grdev01_s.rim",
        "relative_path": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01.rim",
        "destination_name": "grdev01.rim",
        "extra_relative_paths": "artifacts/map_studio/grdev01_exact_stock_module_rename/install/Modules/grdev01_s.rim",
        "extra_destination_names": "grdev01_s.rim",
        "conflicting_destination_names": "grdev01.mod",
        "expected_header": "RIM V1.0",
        "proof_question": "Can KOTOR load the stock root/static RIM pair through custom grdev01 filenames?",
    },
    "renamed-root-minimal": {
        "id": "renamed_root_minimal_git",
        "label": "Renamed grdev01 root MOD using stock rooms and stripped stock GIT runtime lists",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_minimal_git/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a grdev01-root MOD with stock room geometry when dynamic stock GIT lists are stripped?",
    },
    "renamed-root-minimal-placeable": {
        "id": "renamed_root_minimal_git_placeable",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, and one plc_bench test placeable",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_minimal_git_placeable/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a grdev01-root MOD with stock room geometry and one safe authored placeable?",
    },
    "renamed-root-scriptless-minimal": {
        "id": "renamed_root_scriptless_minimal_git",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, and no stock event scripts",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_scriptless_minimal_git/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a grdev01-root MOD with stock room geometry after stock area/module event scripts are cleared?",
    },
    "renamed-root-scriptless-placeable": {
        "id": "renamed_root_scriptless_minimal_git_placeable",
        "label": "Renamed grdev01 root MOD using stock rooms, stripped GIT lists, no stock event scripts, and one plc_bench test placeable",
        "relative_path": "artifacts/map_studio/grdev01_root_unique_id_stock_rooms_scriptless_minimal_git_placeable/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a scriptless grdev01-root stock-room MOD with one safe authored placeable?",
    },
    "renamed-root-scriptless-dual-minimal": {
        "id": "renamed_root_scriptless_dual_minimal_git",
        "label": "Dual-root scriptless MOD using grdev01 and stock m02aa roots with stripped GIT lists",
        "relative_path": "artifacts/map_studio/grdev01_dual_root_scriptless_minimal_git/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a scriptless MOD when both custom grdev01 and stock m02aa root resources are present?",
    },
    "renamed-root-scriptless-dual-placeable": {
        "id": "renamed_root_scriptless_dual_minimal_git_placeable",
        "label": "Dual-root scriptless MOD using grdev01 and stock m02aa roots with one plc_bench test placeable",
        "relative_path": "artifacts/map_studio/grdev01_dual_root_scriptless_minimal_git_placeable/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim,grdev01_s.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can KOTOR load a dual-root scriptless stock-room MOD with one safe authored placeable?",
    },
    "authored-no-marker": {
        "id": "authored_no_marker_candidate",
        "label": "Generated authored room without doorway marker",
        "relative_path": "artifacts/map_studio/grdev01_authored_smoke_no_marker_candidate/install/Modules/grdev01.mod",
        "destination_name": "grdev01.mod",
        "conflicting_destination_names": "grdev01.rim",
        "expected_header": "MOD V1.0",
        "proof_question": "Can GhostRigger's generated room package load once the stock/container handoff is proven?",
    },
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=tuple(VARIANTS), required=True, help="Known grdev01 runtime variant to install.")
    parser.add_argument(
        "--game-root-dir",
        type=Path,
        default=DEFAULT_GAME_ROOT,
        help="KOTOR install root. Ignored when --game-modules-dir is supplied.",
    )
    parser.add_argument(
        "--game-modules-dir",
        type=Path,
        default=None,
        help="Explicit KOTOR Modules folder. Defaults to <game-root-dir>/Modules.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory that receives the install manifest. Defaults under artifacts/map_studio/grdev01_runtime_installs.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Back up and replace an existing active grdev01 package.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report the install plan without copying, backing up, or deleting files.",
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
    if not path.exists():
        return ""
    return path.read_bytes()[:16].decode("ascii", errors="replace").rstrip("\x00")


def _next_backup_path(path: Path) -> Path:
    for index in range(1, 1000):
        candidate = path.with_name(f"{path.name}.bak{index}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find an available backup path for {path}.")


def _files_have_same_bytes(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        return left.read_bytes() == right.read_bytes()
    except OSError:
        return False


def _refresh_currentgame_cache(
    *,
    modules_dir: Path,
    destination: Path,
    extra_destinations: list[Path],
    warnings: list[str],
) -> list[str]:
    refreshed: list[str] = []
    currentgame_dir = modules_dir.parent / "currentgame"
    source_pairs = [(destination.name, destination), *((path.name, path) for path in extra_destinations)]
    for name, installed_path in source_pairs:
        cache_path = currentgame_dir / name
        if not cache_path.exists():
            continue
        if _files_have_same_bytes(cache_path, installed_path):
            warnings.append(
                f"KOTOR currentgame already contains the installed {name}; restart from a clean save if warp testing behaves strangely."
            )
            continue
        backup = _next_backup_path(cache_path)
        shutil.copy2(cache_path, backup)
        shutil.copy2(installed_path, cache_path)
        refreshed.append(str(cache_path))
        warnings.append(f"Refreshed stale KOTOR currentgame cache {name}; backup written to {backup}.")
    return refreshed


def install_variant(
    *,
    variant_key: str,
    game_root_dir: Path = DEFAULT_GAME_ROOT,
    game_modules_dir: Path | None = None,
    output_dir: Path | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    variant = VARIANTS[variant_key]
    source = ROOT / variant["relative_path"]
    modules_dir = game_modules_dir or game_root_dir / "Modules"
    destination_name = variant.get("destination_name", "grdev01.mod")
    extra_relative_paths = [item.strip() for item in variant.get("extra_relative_paths", "").split(",") if item.strip()]
    extra_destination_names = [item.strip() for item in variant.get("extra_destination_names", "").split(",") if item.strip()]
    extra_sources = [ROOT / item for item in extra_relative_paths]
    extra_destinations = [modules_dir / item for item in extra_destination_names]
    conflict_names = [name.strip() for name in variant.get("conflicting_destination_names", "").split(",") if name.strip()]
    destination = modules_dir / destination_name
    output = output_dir or DEFAULT_OUTPUT_ROOT / variant_key
    warnings: list[str] = []
    blocking: list[str] = []
    backup_path = ""
    extra_backup_paths: list[str] = []
    conflict_backup_paths: list[str] = []
    currentgame_refreshed_paths: list[str] = []
    source_header = _header(source)
    source_sha = _sha256(source) if source.exists() else ""
    extra_source_headers = [_header(path) for path in extra_sources]
    extra_source_sha = [_sha256(path) if path.exists() else "" for path in extra_sources]
    installed_sha = ""
    installed_extra_sha: list[str] = []

    if not source.exists():
        blocking.append(f"Staged variant package does not exist: {source}")
    elif not source_header.startswith(variant["expected_header"]):
        blocking.append(
            f"Staged variant {variant_key} has header {source_header!r}; expected {variant['expected_header']!r}."
        )
    if len(extra_sources) != len(extra_destinations):
        blocking.append(f"Variant {variant_key} has mismatched extra source and destination counts.")
    for path, header in zip(extra_sources, extra_source_headers):
        if not path.exists():
            blocking.append(f"Staged companion package does not exist: {path}")
        elif not header.startswith(variant["expected_header"]):
            blocking.append(
                f"Staged companion package {path.name} has header {header!r}; expected {variant['expected_header']!r}."
            )
    existing_conflicts = [modules_dir / name for name in conflict_names if (modules_dir / name).exists()]
    existing_destinations = [path for path in [destination, *extra_destinations] if path.exists()]
    if existing_destinations and not overwrite and not dry_run:
        destination_list = ", ".join(str(path) for path in existing_destinations)
        blocking.append(f"{destination_list} already exists. Re-run with --overwrite to back up and replace them.")
    if existing_conflicts and not overwrite and not dry_run:
        conflict_list = ", ".join(str(path) for path in existing_conflicts)
        blocking.append(f"Conflicting grdev01 package exists ({conflict_list}). Re-run with --overwrite to back it up first.")

    install_plan = {
        "dry_run": bool(dry_run),
        "destination_path": str(destination),
        "destination_exists": destination.exists(),
        "extra_destination_paths": [str(path) for path in extra_destinations],
        "extra_destination_exists": [path.exists() for path in extra_destinations],
        "conflicting_paths": [str(path) for path in existing_conflicts],
        "overwrite_requested": bool(overwrite),
        "would_block_without_overwrite": bool((existing_destinations or existing_conflicts) and not overwrite),
        "would_backup_destination_to": str(_next_backup_path(destination)) if destination.exists() else "",
        "would_backup_extra_destinations_to": [
            {"path": str(path), "backup_path": str(_next_backup_path(path))}
            for path in extra_destinations
            if path.exists()
        ],
        "would_backup_conflicts_to": [
            {"path": str(path), "backup_path": str(_next_backup_path(path))}
            for path in existing_conflicts
        ],
    }

    if not blocking and dry_run:
        warnings.append("Dry run only; no files were copied, backed up, or removed.")

    if not blocking and not dry_run:
        modules_dir.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            backup = _next_backup_path(destination)
            shutil.copy2(destination, backup)
            backup_path = str(backup)
            warnings.append(f"Backed up existing {destination.name} to {backup}.")
        for extra_destination in extra_destinations:
            if extra_destination.exists():
                backup = _next_backup_path(extra_destination)
                shutil.copy2(extra_destination, backup)
                extra_backup_paths.append(str(backup))
                warnings.append(f"Backed up existing {extra_destination.name} to {backup}.")
        for conflict in existing_conflicts:
            backup = _next_backup_path(conflict)
            shutil.copy2(conflict, backup)
            conflict.unlink()
            conflict_backup_paths.append(str(backup))
            warnings.append(f"Backed up and removed conflicting {conflict.name} to {backup}.")
        shutil.copy2(source, destination)
        for extra_source, extra_destination in zip(extra_sources, extra_destinations):
            shutil.copy2(extra_source, extra_destination)
        installed_sha = _sha256(destination)
        installed_extra_sha = [_sha256(path) for path in extra_destinations]
        currentgame_refreshed_paths = _refresh_currentgame_cache(
            modules_dir=modules_dir,
            destination=destination,
            extra_destinations=extra_destinations,
            warnings=warnings,
        )
        if installed_sha != source_sha:
            blocking.append("Installed grdev01.mod hash does not match staged variant hash after copy.")
        for extra_destination, expected_sha, actual_sha in zip(extra_destinations, extra_source_sha, installed_extra_sha):
            if actual_sha != expected_sha:
                blocking.append(f"Installed {extra_destination.name} hash does not match staged variant hash after copy.")

    ok = not blocking
    summary = {
        "ok": ok,
        "code": "planned" if ok and dry_run else "installed" if ok else "blocked",
        "variant": variant_key,
        "variant_id": variant["id"],
        "variant_label": variant["label"],
        "proof_question": variant["proof_question"],
        "source_module_path": str(source),
        "installed_module_path": str(destination) if ok and not dry_run else "",
        "installed_extra_paths": [str(path) for path in extra_destinations] if ok and not dry_run else [],
        "target_module_path": str(destination),
        "target_extra_paths": [str(path) for path in extra_destinations],
        "backup_module_path": backup_path,
        "extra_backup_paths": extra_backup_paths,
        "conflict_backup_paths": conflict_backup_paths,
        "currentgame_refreshed_paths": currentgame_refreshed_paths,
        "install_plan": install_plan,
        "manifest_path": str(output / "grdev01_runtime_variant_install_manifest.json"),
        "source_header": source_header,
        "source_sha256": source_sha,
        "extra_source_headers": extra_source_headers,
        "extra_source_sha256": extra_source_sha,
        "installed_sha256": installed_sha,
        "installed_extra_sha256": installed_extra_sha,
        "warnings": warnings,
        "blocking_issues": blocking,
        "next_actions": [
            "Launch KOTOR and run `warp grdev01`.",
            "Record whether the game loads, crashes, or reaches an infinite loading screen.",
            "Do not mark Map Studio game-tested until the authored generated-room package loads with floor, walkmesh, and test placeable proof.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "kind": "grdev01_runtime_variant_install",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "capability_stage": "diagnostic_package_not_game_verified",
        "summary": summary,
    }
    Path(summary["manifest_path"]).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return summary


def _print_human(summary: dict[str, Any]) -> None:
    status = "OK" if summary["ok"] else "BLOCKED"
    print(f"grdev01 runtime variant install: {status} ({summary['code']})")
    print(f"Variant: {summary['variant']} - {summary['variant_label']}")
    print(f"Question: {summary['proof_question']}")
    print(f"Source: {summary['source_module_path']}")
    print(f"Target: {summary.get('target_module_path') or '(unknown)'}")
    for target in summary.get("target_extra_paths") or []:
        print(f"Companion target: {target}")
    print(f"Installed: {summary['installed_module_path'] or '(not installed)'}")
    for installed in summary.get("installed_extra_paths") or []:
        print(f"Installed companion: {installed}")
    install_plan = summary.get("install_plan") or {}
    if install_plan.get("dry_run"):
        print("Dry run: no files copied")
        print(f"Target exists: {install_plan.get('destination_exists')}")
        print(f"Conflicts: {', '.join(install_plan.get('conflicting_paths') or []) or '(none)'}")
        if install_plan.get("would_backup_destination_to"):
            print(f"Would back up target to: {install_plan['would_backup_destination_to']}")
        for item in install_plan.get("would_backup_conflicts_to") or []:
            print(f"Would back up conflict {item['path']} to: {item['backup_path']}")
        for item in install_plan.get("would_backup_extra_destinations_to") or []:
            print(f"Would back up companion {item['path']} to: {item['backup_path']}")
    if summary["backup_module_path"]:
        print(f"Backup: {summary['backup_module_path']}")
    for extra_backup in summary.get("extra_backup_paths", []):
        print(f"Companion backup: {extra_backup}")
    for conflict_backup in summary.get("conflict_backup_paths", []):
        print(f"Conflict backup: {conflict_backup}")
    print(f"Manifest: {summary['manifest_path']}")
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
    print("Next actions:")
    for action in summary["next_actions"]:
        print(f"- {action}")


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = install_variant(
        variant_key=args.variant,
        game_root_dir=args.game_root_dir,
        game_modules_dir=args.game_modules_dir,
        output_dir=args.output_dir,
        overwrite=bool(args.overwrite),
        dry_run=bool(args.dry_run),
    )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_human(summary)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
